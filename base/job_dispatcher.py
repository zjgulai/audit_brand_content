#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/job_dispatcher.py —— 唯一进程调度与 run_record 作者（T1-03）

## 职责边界（技术方案 §2 #4 / 端到端规格 S1.2–S1.5）

  - 每次 spawn 一个一次性 worker 子进程，**恰好写一条 run_record**；
  - 同一 `case_id` 同时只允许一个 active job：后来的 job **排队等待**，不并行；
  - 只有 worker stdout 是**恰好一个**合法 `ReviewOutput` 且 `run_id` 匹配时，
    才触发 `artifact_store.commit`；
  - worker_crash / timeout / bad_output / commit_failed **只落 run_record**，
    不写回执、不写 `run_state=ERROR`（那是 orchestrator I1–I7 的出口）；
  - 第一阶段**不自动重试、不做 TTL 回收重跑**。

## 本模块不做什么

  - 不构造 Receipt、不生成 receipt_id（orchestrator）；
  - 不判 state / layer / obligations（decision_table）；
  - 不物理追加回执（artifact_store 才是唯一写者）；
  - 不解释 ReviewOutput 的业务语义，只校验外层契约与 run_id。

## ReviewOutput 的边界（照实写）

Playbook §3.3.2 定义的是**七字段**输出契约；调度规格要求 stdout「恰好一个合法
ReviewOutput 且 run_id 匹配」。两者之间 `run_id` 的落点没有逐字规定。本模块取：

    ReviewOutput = Playbook 七字段 + 顶层 `run_id`

并校验：`run_state=ERROR` 时 `state` 与 `external_label` 必须为 null；`run_state=OK`
时 `state` 必须是五档之一。业务字段只做类型/形状校验，不替 orchestrator 判内容。

## run_record

字段固定 14 个（技术方案 §2 #4）：

    run_id / job_id / submission_id / attempt / worker_pid /
    started_at / ended_at / exit_code / signal / outcome /
    stdout_sha256 / stderr_sha256 / receipt_id|null / manifest_ref|null

`outcome` 取值：`succeeded` / `worker_crash` / `timeout` / `bad_output` / `commit_failed`。
`stdout_sha256` / `stderr_sha256` 对**原始字节**取 sha256，失败路径也必须有值。

## 提交什么

成功时提交两项产物：

  - `blobs`：worker stdout 原文（内容寻址，字节级审计锚点）；
  - `receipts`：`ReviewOutput.receipt` 的规范 JSON（不改字段）。

IR 与报告不在这里提交 —— 它们由 orchestrator / report_store 产生；本模块不凭空造字段。
"""
from __future__ import annotations

import hashlib
import json
import os
import signal as signal_mod
import subprocess
import time

RECORD_FIELDS = [
    "run_id", "job_id", "submission_id", "attempt", "worker_pid",
    "started_at", "ended_at", "exit_code", "signal", "outcome",
    "stdout_sha256", "stderr_sha256", "receipt_id", "manifest_ref",
]

OUTCOMES = {"succeeded", "worker_crash", "timeout", "bad_output", "commit_failed"}

FIVE_STATES = {"BLOCK", "REVIEW", "未审查", "待自决", "PASS"}
RUN_STATES = {"OK", "ERROR"}

OUTPUT_FIELDS = [
    "run_id", "findings", "receipt", "state", "run_state",
    "external_label", "obligations", "coverage",
]

HEX64 = set("0123456789abcdef")


def _iso_now():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + ".%06dZ" % (
        int((time.time() % 1) * 1e6))


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _safe_id(s):
    """run_id / receipt_id 会直接拼进数据根下的文件名：只允许安全字符。"""
    if not isinstance(s, str) or not s or s in (".", ".."):
        return False
    return all(c.isalnum() or c in "._-" for c in s)


def _pid_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (ProcessLookupError, ValueError):
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def parse_worker_stdout(stdout, expected_run_id):
    """解析并校验 worker stdout。

    Returns:
        (output_dict, None) 或 (None, reason)。
    """
    if isinstance(stdout, str):
        stdout = stdout.encode("utf-8")
    try:
        text = stdout.decode("utf-8")
    except (UnicodeDecodeError, AttributeError):
        return None, "not_utf8"
    try:
        # json.loads 会拒绝「两个 JSON 值」与任何尾随非空白 —— 正是「恰好一个」。
        obj = json.loads(text)
    except ValueError:
        return None, "not_single_json"
    if not isinstance(obj, dict):
        return None, "not_object"

    missing = [k for k in OUTPUT_FIELDS if k not in obj]
    if missing:
        return None, "missing_fields:" + ",".join(missing)

    rid = obj.get("run_id")
    if not isinstance(rid, str) or not rid:
        return None, "bad_run_id"
    if rid != expected_run_id:
        return None, "run_id_mismatch"

    rs = obj.get("run_state")
    if rs not in RUN_STATES:
        return None, "bad_run_state"
    st = obj.get("state")
    label = obj.get("external_label")
    if rs == "ERROR":
        if st is not None or label is not None:
            return None, "error_must_not_have_state_or_label"
    else:
        if st not in FIVE_STATES:
            return None, "bad_state"
        # Playbook §3.3.2：只有 run_state=ERROR 时 external_label 才允许为 null；
        # run_state=OK 必须有对外标签（与 state 同一封闭五值集合）。
        if label not in FIVE_STATES:
            return None, "bad_external_label"

    if not isinstance(obj.get("findings"), list):
        return None, "bad_findings"
    if not isinstance(obj.get("obligations"), list):
        return None, "bad_obligations"
    if not isinstance(obj.get("coverage"), dict):
        return None, "bad_coverage"
    receipt = obj.get("receipt")
    if not isinstance(receipt, dict):
        return None, "bad_receipt"
    receipt_id = receipt.get("receipt_id")
    if not _safe_id(receipt_id):
        return None, "bad_receipt_id"
    return obj, None


def validate_run_record(rec):
    """run_record 的独立校验；返回错误列表（空 = 通过）。

    本函数**不**被生产路径依赖，但它是「删掉 stdout sha 必须红」这条断言的执行点。
    """
    errs = []
    if not isinstance(rec, dict):
        return ["not_object"]
    keys = set(rec.keys())
    want = set(RECORD_FIELDS)
    if keys != want:
        errs.append("fields:missing=%s extra=%s" % (sorted(want - keys), sorted(keys - want)))
    for k in ("run_id", "job_id", "submission_id"):
        if not isinstance(rec.get(k), str) or not rec.get(k):
            errs.append("bad_%s" % k)
    if not isinstance(rec.get("attempt"), int) or isinstance(rec.get("attempt"), bool) \
            or rec.get("attempt") < 1:
        errs.append("bad_attempt")
    if not isinstance(rec.get("worker_pid"), int) or rec.get("worker_pid") <= 0:
        errs.append("bad_worker_pid")
    for k in ("started_at", "ended_at"):
        v = rec.get(k)
        if not isinstance(v, str) or len(v) < 20 or not v.endswith("Z"):
            errs.append("bad_%s" % k)
    if isinstance(rec.get("started_at"), str) and isinstance(rec.get("ended_at"), str) \
            and rec["ended_at"] < rec["started_at"]:
        errs.append("ended_before_started")
    ec, sig = rec.get("exit_code"), rec.get("signal")
    if not (ec is None or (isinstance(ec, int) and not isinstance(ec, bool) and ec >= 0)):
        errs.append("bad_exit_code")
    if not (sig is None or (isinstance(sig, int) and not isinstance(sig, bool) and sig > 0)):
        errs.append("bad_signal")
    if ec is None and sig is None:
        errs.append("exit_and_signal_both_null")
    if rec.get("outcome") not in OUTCOMES:
        errs.append("bad_outcome")
    for k in ("stdout_sha256", "stderr_sha256"):
        v = rec.get(k)
        if not isinstance(v, str) or len(v) != 64 or not set(v) <= HEX64:
            errs.append("bad_%s" % k)
    rid, mref = rec.get("receipt_id"), rec.get("manifest_ref")
    if not (rid is None or isinstance(rid, str)):
        errs.append("bad_receipt_id")
    if not (mref is None or isinstance(mref, str)):
        errs.append("bad_manifest_ref")
    if rec.get("outcome") == "succeeded":
        if not rid:
            errs.append("succeeded_without_receipt_id")
        if not mref:
            errs.append("succeeded_without_manifest_ref")
    elif rid is not None or mref is not None:
        errs.append("non_succeeded_has_receipt_or_manifest")
    return errs


class DispatcherBusy(Exception):
    """同一 case 在等待窗口内一直有 active job。"""


class JobDispatcher(object):
    def __init__(self, store, state_dir=None, case_wait_timeout=300.0, poll_interval=0.05,
                 lock_stale_seconds=3600.0):
        self.store = store
        self.state_dir = os.path.abspath(state_dir or os.path.join(store.root, "dispatch"))
        self.locks_dir = os.path.join(self.state_dir, "locks")
        os.makedirs(self.locks_dir, exist_ok=True)
        self.records_path = os.path.join(self.state_dir, "run-records.jsonl")
        self.case_wait_timeout = float(case_wait_timeout)
        self.poll_interval = float(poll_interval)
        self.lock_stale_seconds = float(lock_stale_seconds)

    # ── per-case 串行锁 ────────────────────────────────────────────────
    def _lock_path(self, case_id):
        h = hashlib.sha256(case_id.encode("utf-8")).hexdigest()[:24]
        return os.path.join(self.locks_dir, h + ".lock")

    def _try_acquire(self, path):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            return None
        try:
            payload = json.dumps({"pid": os.getpid(), "ts": time.time()}).encode("utf-8")
            os.write(fd, payload)
            os.fsync(fd)
            ino = os.fstat(fd).st_ino
        finally:
            os.close(fd)
        return ino

    def _stale(self, path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            pid = data.get("pid")
            ts = data.get("ts")
        except (OSError, ValueError):
            pid = None
            ts = None
        if isinstance(pid, int) and _pid_alive(pid):
            return False
        if isinstance(pid, int):
            return True  # 死 PID：立即视为陈旧
        if ts is None:
            try:
                ts = os.path.getmtime(path)
            except OSError:
                return False
        return (time.time() - float(ts)) > self.lock_stale_seconds

    def _acquire_case(self, case_id):
        path = self._lock_path(case_id)
        deadline = time.monotonic() + self.case_wait_timeout
        while True:
            ino = self._try_acquire(path)
            if ino is not None:
                return path, ino
            if self._stale(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass
                continue
            if time.monotonic() >= deadline:
                raise DispatcherBusy("case %r 仍有 active job（等待 %.1fs）"
                                     % (case_id, self.case_wait_timeout))
            time.sleep(self.poll_interval)

    def _release_case(self, path, ino):
        try:
            if os.stat(path).st_ino == ino:
                os.unlink(path)
        except OSError:
            pass

    # ── run_record ────────────────────────────────────────────────────
    def _append_record(self, rec):
        data = (json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        fd = os.open(self.records_path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        try:
            view = memoryview(data)
            while view:
                n = os.write(fd, view)
                view = view[n:]
            os.fsync(fd)
        finally:
            os.close(fd)

    # ── 主入口 ────────────────────────────────────────────────────────
    def run(self, case_id, submission_id, run_id, command, attempt=1, job_id=None,
            timeout=300.0, extra_env=None, cwd=None):
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("case_id 必须是非空字符串")
        if not isinstance(submission_id, str) or not submission_id:
            raise ValueError("submission_id 必须是非空字符串")
        if not _safe_id(run_id):
            raise ValueError("run_id 只允许 [A-Za-z0-9._-]：%r" % (run_id,))
        if not isinstance(command, (list, tuple)) or not command \
                or not all(isinstance(a, str) for a in command):
            raise ValueError("command 必须是字符串列表")
        if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
            raise ValueError("attempt 必须是 >=1 的整数")
        timeout = float(timeout)
        if timeout <= 0:
            raise ValueError("timeout 必须 > 0")
        if self.store.read_manifest(run_id) is not None:
            raise ValueError("run_id 已提交过：%r（run_id 必须唯一）" % (run_id,))

        lock_path, ino = self._acquire_case(case_id)
        try:
            rec = self._run_locked(case_id, submission_id, run_id, list(command),
                                   attempt, job_id, timeout, extra_env, cwd)
            # ★ 记录在锁内追加：同一 case 的记录顺序 = 实际执行顺序。
            self._append_record(rec)
            return rec
        finally:
            self._release_case(lock_path, ino)

    def _run_locked(self, case_id, submission_id, run_id, command, attempt,
                    job_id, timeout, extra_env, cwd):
        env = os.environ.copy()
        env.update({
            "AUDIT_CASE_ID": case_id,
            "AUDIT_SUBMISSION_ID": submission_id,
            "AUDIT_RUN_ID": run_id,
            "AUDIT_ATTEMPT": str(attempt),
        })
        for k, v in (extra_env or {}).items():
            env[str(k)] = str(v)

        started_at = _iso_now()
        try:
            proc = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=env, cwd=cwd, start_new_session=True)
        except OSError as e:
            raise RuntimeError("spawn 失败（未产生 run_record）：%s" % e)
        worker_pid = proc.pid

        timed_out = False
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(os.getpgid(worker_pid), signal_mod.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                try:
                    proc.kill()
                except OSError:
                    pass
            out, err = proc.communicate()
        ended_at = _iso_now()

        rc = proc.returncode
        if rc is not None and rc < 0:
            exit_code, sig = None, -rc
        else:
            exit_code, sig = rc, None

        job_id = job_id or ("job_" + hashlib.sha256(
            (case_id + "\n" + run_id).encode("utf-8")).hexdigest()[:16])
        rec = {
            "run_id": run_id,
            "job_id": job_id,
            "submission_id": submission_id,
            "attempt": attempt,
            "worker_pid": worker_pid,
            "started_at": started_at,
            "ended_at": ended_at,
            "exit_code": exit_code,
            "signal": sig,
            "outcome": None,
            "stdout_sha256": _sha256(out),
            "stderr_sha256": _sha256(err),
            "receipt_id": None,
            "manifest_ref": None,
        }

        if timed_out:
            rec["outcome"] = "timeout"
            return rec
        if rc != 0:
            rec["outcome"] = "worker_crash"
            return rec

        parsed, _reason = parse_worker_stdout(out, run_id)
        if parsed is None:
            rec["outcome"] = "bad_output"
            return rec

        receipt = parsed["receipt"]
        receipt_bytes = json.dumps(
            receipt, ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode("utf-8")
        artifacts = [
            {"kind": "blobs", "key": "review-output", "data": out},
            {"kind": "receipts", "key": receipt["receipt_id"], "data": receipt_bytes},
        ]
        try:
            self.store.commit(run_id, artifacts)
        except Exception:  # noqa: BLE001
            # 提交失败是「不知道有没有落全」：run_record 仍要留，且不写 receipt_id/manifest_ref。
            rec["outcome"] = "commit_failed"
            return rec

        rec["outcome"] = "succeeded"
        rec["receipt_id"] = receipt["receipt_id"]
        rec["manifest_ref"] = os.path.join("manifests", run_id + ".json")
        return rec
