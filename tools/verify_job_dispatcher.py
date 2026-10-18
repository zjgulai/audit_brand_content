#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_job_dispatcher.py —— `base/job_dispatcher.py` 的判据（T1-03）

## 它验什么

  A **成功路径**：spawn 一次 → 恰好一条 run_record；worker stdout 是恰好一个
    合法 ReviewOutput 且 run_id 匹配 → 触发 artifact_store.commit，manifest 可读回。
  B **失败路径**：worker_crash / timeout / bad_output 都不 commit，只落 run_record；
    outcome / exit_code / signal / stdout_sha256 必须是实测值，不是 0 或空串。
  C **串行**：同一 case 两个并发 job 必须排队，worker 执行区间不重叠，两条都成功。
  D **反向对照**：删掉 stdout_sha256 → 记录校验必须红；两个 ReviewOutput / run_id
    不匹配 / ERROR 仍带 state → 必须判 bad_output 且不 commit。
  E **不自动重试**：崩溃的 worker 只被 spawn 一次。

## 退出码

  0 全过 · 1 有红 · 2 未测（建不出临时目录 / 起不了子进程）

## 口径

  - 纯离线、纯 stdlib；所有产物落在临时目录。
  - 哈希由本脚本**独立重算**（不信 run_record 自报）。
  - run_record 字段表在本脚本里**再写一遍**，不 import 被测模块的常量 ——
    否则删掉模块里的字段，常量跟着少，断言恒真。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest.mock as mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "base"))

try:
    from artifact_store import ArtifactStore
    from job_dispatcher import (
        DispatcherBusy, JobDispatcher, parse_worker_stdout, validate_run_record)
except Exception as e:  # noqa: BLE001
    print("❌ 导入 base/job_dispatcher.py 失败：%s" % e)
    sys.exit(1)

# ★ 独立字段表：不 import 被测模块的 RECORD_FIELDS。
FIELDS = [
    "run_id", "job_id", "submission_id", "attempt", "worker_pid",
    "started_at", "ended_at", "exit_code", "signal", "outcome",
    "stdout_sha256", "stderr_sha256", "receipt_id", "manifest_ref",
]
HEX64 = set("0123456789abcdef")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def is_iso(s):
    return (isinstance(s, str) and len(s) >= 20 and s[4] == "-" and s[7] == "-"
            and s[10] == "T" and s.endswith("Z"))


def lines(path):
    try:
        with open(path, encoding="utf-8") as f:
            return [ln for ln in f.read().splitlines() if ln.strip()]
    except OSError:
        return []


def main():
    try:
        TMP = tempfile.mkdtemp(prefix="jobdisp_")
    except OSError as e:
        print("⚠ 未测：建不出临时目录（%s）" % e)
        return 2

    fails = []
    checks = 0
    untested = []

    def T(cid, ok, detail=""):
        nonlocal checks
        checks += 1
        if not ok:
            fails.append("%s  %s" % (cid, detail))

    def worker(name, body):
        p = os.path.join(TMP, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write("import json, os, sys, time\n" + body)
        return p

    def new_store(tag):
        d = os.path.join(TMP, "data_" + tag)
        os.makedirs(d, exist_ok=True)
        return ArtifactStore(d)

    def new_disp(tag, store):
        return JobDispatcher(store, state_dir=os.path.join(TMP, "state_" + tag),
                             case_wait_timeout=10.0, poll_interval=0.02)

    def output_json(run_id, receipt_id="rcpt_1", **over):
        out = {
            "run_id": run_id,
            "findings": [],
            "receipt": {"receipt_id": receipt_id, "unit_id": "u1"},
            "state": "PASS",
            "run_state": "OK",
            "external_label": "PASS",
            "obligations": [],
            "coverage": {"coverage_state": "full"},
        }
        out.update(over)
        return json.dumps(out, ensure_ascii=False, sort_keys=True)

    def runtime_worker(name):
        """输出在**运行时**按 AUDIT_RUN_ID 组装；用于不同 run_id 的多个用例。"""
        return worker(name, (
            "rid = os.environ['AUDIT_RUN_ID']\n"
            "out = {'run_id': rid, 'findings': [],"
            " 'receipt': {'receipt_id': 'rcpt_' + rid, 'unit_id': 'u1'},"
            " 'state': 'PASS', 'run_state': 'OK', 'external_label': 'PASS',"
            " 'obligations': [], 'coverage': {'coverage_state': 'full'}}\n"
            "sys.stdout.write(json.dumps(out, ensure_ascii=False, sort_keys=True) + '\\n')\n"
        ))

    # ── A 成功路径 ────────────────────────────────────────────────────
    store = new_store("ok")
    disp = new_disp("ok", store)
    out_file = os.path.join(TMP, "stdout_ok.txt")
    w = worker("w_ok.py", (
        "rid = os.environ['AUDIT_RUN_ID']\n"
        "p = %r\n"
        "open(os.environ['AUDIT_OUT_FILE'], 'w', encoding='utf-8').write(p + '\\n')\n"
        "sys.stdout.write(p + '\\n')\n"
    ) % output_json("RUN_OK"))
    env = {"AUDIT_OUT_FILE": out_file}
    rec = disp.run(case_id="case_ok", submission_id="sub_ok", run_id="RUN_OK",
                   command=[sys.executable, w], timeout=10, extra_env=env)
    raw_out = open(out_file, "rb").read()

    T("A1 run_record 字段恰好 14 个", sorted(rec.keys()) == sorted(FIELDS),
      "keys=%s" % sorted(rec.keys()))
    T("A2 outcome=succeeded、exit_code=0、signal=null",
      rec.get("outcome") == "succeeded" and rec.get("exit_code") == 0
      and rec.get("signal") is None, json.dumps(rec, ensure_ascii=False))
    T("A3 stdout_sha256 == 独立重算", rec.get("stdout_sha256") == sha(raw_out),
      "rec=%s actual=%s" % (rec.get("stdout_sha256"), sha(raw_out)))
    T("A4 stderr_sha256 == 空串 sha", rec.get("stderr_sha256") == sha(b""),
      str(rec.get("stderr_sha256")))
    T("A5 run_id / job_id / submission_id / attempt",
      rec.get("run_id") == "RUN_OK" and isinstance(rec.get("job_id"), str)
      and rec.get("job_id") and rec.get("submission_id") == "sub_ok"
      and rec.get("attempt") == 1, json.dumps(rec, ensure_ascii=False))
    T("A6 worker_pid 是正整数", isinstance(rec.get("worker_pid"), int) and rec["worker_pid"] > 0,
      str(rec.get("worker_pid")))
    T("A7 started_at / ended_at 是 ISO-Z 且结束不早于开始",
      is_iso(rec.get("started_at")) and is_iso(rec.get("ended_at"))
      and rec["ended_at"] >= rec["started_at"], "%s / %s" % (rec.get("started_at"), rec.get("ended_at")))
    T("A8 receipt_id / manifest_ref 非空",
      rec.get("receipt_id") == "rcpt_1"
      and rec.get("manifest_ref") == "manifests/RUN_OK.json",
      "%s / %s" % (rec.get("receipt_id"), rec.get("manifest_ref")))
    T("A9 恰好一条 run_record", len(lines(os.path.join(TMP, "state_ok", "run-records.jsonl"))) == 1,
      str(len(lines(os.path.join(TMP, "state_ok", "run-records.jsonl")))))
    T("A10 validate_run_record 对产物返回空错误", validate_run_record(rec) == [],
      str(validate_run_record(rec)))

    man = store.read_manifest("RUN_OK")
    T("A11 manifest 已提交且可读", isinstance(man, dict) and man.get("run_id") == "RUN_OK",
      str(man)[:200])
    entries = (man or {}).get("entries", [])
    paths = [e.get("path") for e in entries]
    T("A12 manifest 含 stdout blob 与 receipt 两项", len(entries) == 2
      and any(p.startswith("blobs/") for p in paths)
      and any(p == "receipts/rcpt_1.json" for p in paths), str(paths))
    blob_path = next((os.path.join(store.root, p) for p in paths if p.startswith("blobs/")), None)
    T("A13 blob 内容 == worker stdout 原文",
      blob_path is not None and open(blob_path, "rb").read() == raw_out, str(blob_path))
    rpath = os.path.join(store.root, "receipts", "rcpt_1.json")
    T("A14 receipt 内容读回 == stdout 里的 receipt（不改内容）",
      os.path.exists(rpath) and json.load(open(rpath, encoding="utf-8"))
      == json.loads(raw_out.decode("utf-8"))["receipt"], rpath)
    # 同一 run_id 再跑必须拒绝（manifest 是唯一不可变提交点，不许覆盖）
    rejected = False
    try:
        disp.run(case_id="case_ok", submission_id="sub_ok", run_id="RUN_OK",
                 command=[sys.executable, w], timeout=10,
                 extra_env={"AUDIT_OUT_FILE": out_file + ".2"})
    except ValueError:
        rejected = True
    T("A15 同一 run_id 第二次运行被拒绝（不覆盖已提交 manifest）", rejected, "")
    T("A15b 被拒绝时没有多写 run_record",
      len(lines(os.path.join(TMP, "state_ok", "run-records.jsonl"))) == 1, "")

    # ── A16/A17 陈旧锁：死 PID 必须清、活 PID 必须等 ─────────────────
    w_rt = runtime_worker("w_runtime.py")

    # 先拿一个「确定已死」的 pid：起一个立刻退出的子进程，用它退场后的 pid。
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    dead_pid = dead.pid

    store = new_store("stalelock")
    state = os.path.join(TMP, "state_stalelock")
    disp = JobDispatcher(store, state_dir=state, case_wait_timeout=1.0, poll_interval=0.01)
    lock = disp._lock_path("case_stale")
    os.makedirs(os.path.dirname(lock), exist_ok=True)
    with open(lock, "w", encoding="utf-8") as f:
        json.dump({"pid": dead_pid, "ts": time.time()}, f)
    err = None
    try:
        rec_stale = disp.run(case_id="case_stale", submission_id="s", run_id="RUN_STALE",
                             command=[sys.executable, w_rt], timeout=10)
    except Exception as e:  # noqa: BLE001
        rec_stale, err = None, e
    T("A16 死 PID 陈旧锁被清理，job 能跑成功",
      err is None and rec_stale is not None and rec_stale.get("outcome") == "succeeded"
      and not os.path.exists(lock), "err=%r rec=%r lock_exists=%s"
      % (err, rec_stale, os.path.exists(lock)))

    store = new_store("livelock")
    state = os.path.join(TMP, "state_livelock")
    disp = JobDispatcher(store, state_dir=state, case_wait_timeout=0.15, poll_interval=0.01)
    lock = disp._lock_path("case_live")
    os.makedirs(os.path.dirname(lock), exist_ok=True)
    with open(lock, "w", encoding="utf-8") as f:
        json.dump({"pid": os.getpid(), "ts": time.time()}, f)
    t0 = time.time()
    err = None
    try:
        disp.run(case_id="case_live", submission_id="s", run_id="RUN_LIVE",
                 command=[sys.executable, w_rt], timeout=10)
    except DispatcherBusy as e:
        err = e
    elapsed_live = time.time() - t0
    T("A17 活 PID 锁不被删，等锁超时抛 DispatcherBusy",
      isinstance(err, DispatcherBusy) and os.path.exists(lock) and elapsed_live >= 0.10,
      "err=%r lock_exists=%s elapsed=%.3fs" % (err, os.path.exists(lock), elapsed_live))
    T("A17b 等锁失败期间没有 spawn（run_record 不存在）",
      not os.path.exists(os.path.join(state, "run-records.jsonl")), "")

    # ── A18 commit 抛异常 → commit_failed，不写 receipt/manifest ─────
    store = new_store("commitfail")
    disp = new_disp("commitfail", store)
    with mock.patch.object(store, "commit", side_effect=RuntimeError("boom")):
        rec_cf = disp.run(case_id="case_cf", submission_id="s", run_id="RUN_CF",
                          command=[sys.executable, w_rt], timeout=10)
    T("A18a commit 异常 → outcome=commit_failed",
      rec_cf.get("outcome") == "commit_failed", json.dumps(rec_cf, ensure_ascii=False))
    T("A18b commit_failed 的 receipt_id / manifest_ref 均为 null",
      rec_cf.get("receipt_id") is None and rec_cf.get("manifest_ref") is None, "")
    T("A18c commit 失败仍恰好写一条 run_record",
      len(lines(os.path.join(TMP, "state_commitfail", "run-records.jsonl"))) == 1, "")
    T("A18d commit 失败没有 manifest",
      store.read_manifest("RUN_CF") is None, "")

    # ── B1 两个 ReviewOutput → bad_output，不 commit ─────────────────
    store = new_store("two")
    disp = new_disp("two", store)
    one = output_json("RUN_TWO", "rcpt_two")
    w = worker("w_two.py", (
        "p = %r\nsys.stdout.write(p + '\\n' + p + '\\n')\n"
    ) % one)
    rec = disp.run(case_id="case_two", submission_id="s", run_id="RUN_TWO",
                   command=[sys.executable, w], timeout=10)
    T("B1a 两个 JSON → bad_output",
      rec.get("outcome") == "bad_output" and rec.get("receipt_id") is None
      and rec.get("manifest_ref") is None, json.dumps(rec, ensure_ascii=False))
    T("B1b bad_output 不 commit", store.read_manifest("RUN_TWO") is None, "")
    T("B1c stdout_sha256 仍是实测值", rec.get("stdout_sha256") == sha((one + "\n" + one + "\n").encode()),
      str(rec.get("stdout_sha256")))

    # ── B2 run_id 不匹配 → bad_output ───────────────────────────────
    store = new_store("mismatch")
    disp = new_disp("mismatch", store)
    w = worker("w_mismatch.py", (
        "p = %r\nsys.stdout.write(p + '\\n')\n"
    ) % output_json("OTHER_RUN"))
    rec = disp.run(case_id="case_mm", submission_id="s", run_id="RUN_MM",
                   command=[sys.executable, w], timeout=10)
    T("B2a run_id 不匹配 → bad_output", rec.get("outcome") == "bad_output",
      json.dumps(rec, ensure_ascii=False))
    T("B2b run_id 不匹配不 commit", store.read_manifest("RUN_MM") is None, "")

    # ── B3 非零退出 → worker_crash ──────────────────────────────────
    store = new_store("crash")
    disp = new_disp("crash", store)
    marker = os.path.join(TMP, "crash_marker")
    w = worker("w_crash.py", (
        "open(%r, 'a').write('attempt\\n')\nsys.stderr.write('boom')\nsys.exit(7)\n"
    ) % marker)
    rec = disp.run(case_id="case_crash", submission_id="s", run_id="RUN_CRASH",
                   command=[sys.executable, w], timeout=10)
    T("B3a 非零退出 → worker_crash、exit_code=7、signal=null",
      rec.get("outcome") == "worker_crash" and rec.get("exit_code") == 7
      and rec.get("signal") is None, json.dumps(rec, ensure_ascii=False))
    T("B3b stderr_sha256 == 实测 stderr", rec.get("stderr_sha256") == sha(b"boom"),
      str(rec.get("stderr_sha256")))
    T("B3c worker_crash 不 commit", store.read_manifest("RUN_CRASH") is None, "")
    T("B3d 不自动重试（worker 只被 spawn 一次）", lines(marker) == ["attempt"], str(lines(marker)))

    # ── B4 超时 → timeout，进程被杀 ─────────────────────────────────
    store = new_store("timeout")
    disp = new_disp("timeout", store)
    tmarker = os.path.join(TMP, "timeout_marker")
    w = worker("w_timeout.py", (
        "open(%r, 'a').write('start\\n')\ntime.sleep(5)\nopen(%r, 'a').write('end\\n')\n"
    ) % (tmarker, tmarker))
    t0 = time.time()
    rec = disp.run(case_id="case_to", submission_id="s", run_id="RUN_TO",
                   command=[sys.executable, w], timeout=0.4)
    elapsed = time.time() - t0
    T("B4a 超时 → timeout", rec.get("outcome") == "timeout", json.dumps(rec, ensure_ascii=False))
    T("B4b 超时后进程被 SIGKILL（signal=9）", rec.get("signal") == 9
      and rec.get("exit_code") is None, "%s / %s" % (rec.get("exit_code"), rec.get("signal")))
    T("B4c 超时在 timeout 附近返回（<3s）", elapsed < 3.0, "%.2fs" % elapsed)
    T("B4d 超时 worker 没有跑完（无 end 行）", lines(tmarker) == ["start"], str(lines(tmarker)))
    T("B4e timeout 不 commit", store.read_manifest("RUN_TO") is None, "")

    # ── B5 回执缺 receipt_id → bad_output ────────────────────────────
    store = new_store("badreceipt")
    disp = new_disp("badreceipt", store)
    bad = output_json("RUN_BR", receipt_id=None)
    w = worker("w_badreceipt.py", (
        "p = %r\nsys.stdout.write(p + '\\n')\n"
    ) % bad)
    rec = disp.run(case_id="case_br", submission_id="s", run_id="RUN_BR",
                   command=[sys.executable, w], timeout=10)
    T("B5 回执缺 receipt_id → bad_output", rec.get("outcome") == "bad_output",
      json.dumps(rec, ensure_ascii=False))

    # ── B6 receipt_id 路径穿越 → bad_output，且不许写出数据根 ─────────
    store = new_store("trav")
    disp = new_disp("trav", store)
    trav = output_json("RUN_TRAV", receipt_id="../../evil")
    w = worker("w_trav.py", (
        "p = %r\nsys.stdout.write(p + '\\n')\n"
    ) % trav)
    rec = disp.run(case_id="case_trav", submission_id="s", run_id="RUN_TRAV",
                   command=[sys.executable, w], timeout=10)
    outside = os.path.join(os.path.dirname(store.root), "evil.json")
    T("B6a receipt_id 含 ../ → bad_output", rec.get("outcome") == "bad_output",
      json.dumps(rec, ensure_ascii=False))
    T("B6b 没有文件被写到数据根外", not os.path.exists(outside), outside)
    T("B6c B1–B6 每个失败 attempt 都恰好一条 run_record",
      all(len(lines(os.path.join(TMP, "state_" + t, "run-records.jsonl"))) == 1
          for t in ("two", "mismatch", "crash", "timeout", "badreceipt", "trav")),
      str({t: len(lines(os.path.join(TMP, "state_" + t, "run-records.jsonl")))
           for t in ("two", "mismatch", "crash", "timeout", "badreceipt", "trav")}))

    # ── C 同一 case 两个 job 并发 → 串行排队 ─────────────────────────
    store = new_store("serial")
    smarker = os.path.join(TMP, "serial_marker")
    sw = worker("w_serial.py", (
        "rid = os.environ['AUDIT_RUN_ID']\n"
        "out = {'run_id': rid, 'findings': [],"
        " 'receipt': {'receipt_id': 'rcpt_' + rid, 'unit_id': 'u1'},"
        " 'state': 'PASS', 'run_state': 'OK', 'external_label': 'PASS',"
        " 'obligations': [], 'coverage': {'coverage_state': 'full'}}\n"
        "open(%r, 'a').write('start %%d %%.6f\\n' %% (os.getpid(), time.time()))\n"
        "time.sleep(0.30)\n"
        "open(%r, 'a').write('end %%d %%.6f\\n' %% (os.getpid(), time.time()))\n"
        "p = json.dumps(out, ensure_ascii=False, sort_keys=True)\n"
        "open(os.environ['AUDIT_OUT_FILE'], 'w', encoding='utf-8').write(p + '\\n')\n"
        "sys.stdout.write(p + '\\n')\n"
    ) % (smarker, smarker))
    driver = os.path.join(TMP, "driver.py")
    with open(driver, "w", encoding="utf-8") as f:
        f.write(
            "import json, os, sys\n"
            "sys.path.insert(0, %r)\n"
            "from artifact_store import ArtifactStore\n"
            "from job_dispatcher import JobDispatcher\n"
            "store = ArtifactStore(%r)\n"
            "d = JobDispatcher(store, state_dir=%r, case_wait_timeout=10.0, poll_interval=0.02)\n"
            "rec = d.run(case_id='case_serial', submission_id='s', run_id=sys.argv[1],\n"
            "            command=[sys.executable, %r], timeout=10,\n"
            "            extra_env={'AUDIT_OUT_FILE': os.path.join(%r, 'serial_'+sys.argv[1]+'.txt')})\n"
            "print(json.dumps(rec))\n"
            % (os.path.join(ROOT, "base"), store.root, os.path.join(TMP, "state_serial"),
               sw, TMP))
    env = dict(os.environ, AUDIT_MARKER=smarker)
    procs = [subprocess.Popen([sys.executable, driver, rid], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=env)
             for rid in ("RUN_S1", "RUN_S2")]
    outs = []
    for p in procs:
        so, se = p.communicate(timeout=20)
        outs.append((p.returncode, so.decode("utf-8", "replace"), se.decode("utf-8", "replace")))
    T("C1 两个并发 driver 都退 0", all(rc == 0 for rc, _, _ in outs),
      str([(rc, se[-120:]) for rc, _, se in outs]))
    recs = []
    for rc, so, se in outs:
        try:
            recs.append(json.loads(so.strip().splitlines()[-1]))
        except Exception:
            recs.append({})
    T("C2 两个 job 都成功", all(r.get("outcome") == "succeeded" for r in recs),
      json.dumps(recs, ensure_ascii=False)[:300])
    marks = lines(smarker)
    T("C3 marker 恰有 2 组 start/end", len(marks) == 4, str(marks))
    intervals = {}
    for ln in marks:
        kind, pid, t = ln.split()
        intervals.setdefault(pid, {})[kind] = float(t)
    ok_serial = len(intervals) == 2 and all({"start", "end"} <= set(v) for v in intervals.values())
    if ok_serial:
        a, b = list(intervals.values())
        overlap = a["start"] < b["end"] and b["start"] < a["end"]
        ok_serial = not overlap
    T("C4 worker 执行区间不重叠（同一 case 串行）", ok_serial, str(intervals))
    T("C5 两条 run_record 都落盘",
      len(lines(os.path.join(TMP, "state_serial", "run-records.jsonl"))) == 2,
      str(len(lines(os.path.join(TMP, "state_serial", "run-records.jsonl")))))
    T("C6 两个 manifest 都已提交",
      store.read_manifest("RUN_S1") is not None and store.read_manifest("RUN_S2") is not None, "")

    # ── D 反向对照：断言自己不许恒真 ────────────────────────────────
    T("D1 删掉 stdout_sha256 → validate_run_record 必须报错",
      validate_run_record({k: v for k, v in recs[0].items() if k != "stdout_sha256"}) != [], "")
    T("D2 把 stdout_sha256 改成非法值 → 必须报错",
      validate_run_record(dict(recs[0], stdout_sha256="0" * 63)) != [], "")
    ok, why = parse_worker_stdout((one + "\n" + one + "\n").encode(), "RUN_TWO")
    T("D3 两个 ReviewOutput → parse 必须拒", ok is None, str(why))
    ok, why = parse_worker_stdout(output_json("OTHER").encode(), "WANTED")
    T("D4 run_id 不匹配 → parse 必须拒", ok is None, str(why))
    ok, why = parse_worker_stdout(output_json("R", state="PASS", run_state="ERROR").encode(), "R")
    T("D5 ERROR 仍带 state → parse 必须拒", ok is None, str(why))
    ok, why = parse_worker_stdout(b"not json", "R")
    T("D6 非 JSON → parse 必须拒", ok is None, str(why))
    ok, why = parse_worker_stdout(output_json("R").encode(), "R")
    T("D7 合法输出 → parse 通过（反向对照：不是恒拒）", isinstance(ok, dict), str(why))
    ok, why = parse_worker_stdout(output_json("R", external_label="BAD").encode(), "R")
    T("D8 external_label 不在五值内 → parse 必须拒", ok is None, str(why))
    ok, why = parse_worker_stdout(output_json("R", external_label=None).encode(), "R")
    T("D9 run_state=OK 且 external_label=null → parse 必须拒", ok is None, str(why))
    ok, why = parse_worker_stdout(
        output_json("R", run_state="ERROR", state=None, external_label=None).encode(), "R")
    T("D10 run_state=ERROR 且 state/label=null → parse 通过（反向对照）",
      isinstance(ok, dict), str(why))
    T("D8 成功记录不得有未测的哈希", recs[0].get("stdout_sha256")
      and set(recs[0]["stdout_sha256"]) <= HEX64 and len(recs[0]["stdout_sha256"]) == 64, "")

    # ── 结论 ────────────────────────────────────────────────────────
    for f in fails:
        print("  ❌ " + f)
    if untested:
        for u in untested:
            print("  ⚠ " + u)
    verdict = "❌" if fails else ("⚠" if untested else "✅")
    print("\n%s verify_job_dispatcher %d 项检查 · %d 项红 · 临时目录 %s"
          % (verdict, checks, len(fails), os.path.basename(TMP)))
    if fails:
        return 1
    return 2 if untested else 0


if __name__ == "__main__":
    try:
        rc = main()
    except subprocess.TimeoutExpired as e:
        print("⚠ 未测：子进程等待超时（%s）—— 不是通过" % e)
        rc = 2
    if os.environ.get("JOB_DISP_KEEP_TMP") != "1":
        pass  # 由 main 内的 TMP 变量无法在此清理；保留临时目录便于复现
    sys.exit(rc)
