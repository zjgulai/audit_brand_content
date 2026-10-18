#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/submission_router.py — T1-01：入口四维校验 + Attempt 唯一写者

边界：
- 只做入口校验与 Attempt 记账；不解析、不判定、不产 IR。
- 四维取值域全部来自 `base/contract.py`（CONTENT_TYPES / CONTENT_STAGES /
  ENTRY_CHANNELS / SOURCE_KIND_DOMAIN），本文件不抄第二份。
- NAS / 上传文件 / source.kind=文档 是**显式 unsupported**：必须记
  `outcome=rejected_unsupported`、`failure_kind=unsupported`，不得静默成功或丢弃。
- Attempt 字段固定为 §1bis.2 的 8 个；`submission_router` 是唯一写者，
  `attempts` 只返回深拷贝，外部改不动内部状态。

恒等式（L1-7 的唯一依据）：
    accepted + rejected_unsupported + failed == 入口提交总数
    Σ attempt(failure_kind=k) for k in 四值 == 报告那一行

读不出 Attempt 源时抛 `AttemptReadError`，由上层显示「未测」，**不许显示 0**。
"""

from __future__ import annotations

import copy
import hashlib
import os
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from base import contract as C  # noqa: E402

ATTEMPT_FIELDS = (
    "attempt_id",
    "submission_id",
    "entered_at",
    "outcome",
    "failure_kind",
    "reason",
    "ir_id",
    "receipt_id",
)

CONTENT_TYPES = C.CONTENT_TYPES
CONTENT_STAGES = C.CONTENT_STAGES
ENTRY_CHANNEL_DOMAIN = C.ENTRY_CHANNELS
SOURCE_KIND_DOMAIN = C.SOURCE_KIND_DOMAIN
UNSUPPORTED_ENTRY_CHANNELS = frozenset(C.UNSUPPORTED_ENTRY_CHANNELS)
UNSUPPORTED_SOURCE_KINDS = frozenset(C.UNSUPPORTED_SOURCE_KINDS)
OUTCOMES = C.OUTCOMES
FAILURE_KINDS = C.FAILURE_KINDS

# 「无信息词」：报告里出现它等于没写原因。
BANNED_REASONS = ("其他", "其他错误", "未知", "未知错误")


class AttemptReadError(Exception):
    """Attempt 源读不出（缺失/损坏/字段不认识）—— 上层必须显示「未测」。"""


def _reason_problem(reason):
    if not isinstance(reason, str) or not reason.strip():
        return "reason 必须是非空字符串"
    rs = reason.strip()
    if rs in BANNED_REASONS or "未知错误" in rs:
        return "reason 不许写「其他 / 未知错误」这类无信息词：%r" % reason
    return None


def _entry_problems(submission):
    """四维校验；返回问题清单（空 = 全部在取值域内）。"""
    p = []
    if not isinstance(submission, dict):
        return ["submission 必须是 dict，收到 %s" % type(submission).__name__]
    sid = submission.get("submission_id")
    if not isinstance(sid, str) or not sid.strip():
        p.append("submission_id 必须是非空字符串：%r" % (sid,))
    for field, domain in (
            ("content_type", CONTENT_TYPES),
            ("content_stage", CONTENT_STAGES),
            ("entry_channel", ENTRY_CHANNEL_DOMAIN)):
        value = submission.get(field)
        if value not in domain:
            p.append("%s=%r 不在取值域 %r" % (field, value, domain))
    source = submission.get("source")
    kind = source.get("kind") if isinstance(source, dict) else None
    if kind not in SOURCE_KIND_DOMAIN:
        p.append("source.kind=%r 不在取值域 %r" % (kind, SOURCE_KIND_DOMAIN))
    return p


def classify_submission(submission, failure_kind=None):
    """返回 {outcome, failure_kind?, reason}；不写盘、不改状态。

    ★ 这是「unsupported 不得静默成功」的唯一判定点：
      取不到的值、显式不做的通道/来源，都必须落 rejected_unsupported。
    """
    problems = _entry_problems(submission)
    if problems:
        return {
            "outcome": "rejected_unsupported",
            "failure_kind": "unsupported",
            "reason": "input rejected as unsupported: " + "; ".join(problems),
        }

    channel = submission.get("entry_channel")
    kind = submission.get("source", {}).get("kind")
    if channel in UNSUPPORTED_ENTRY_CHANNELS:
        return {
            "outcome": "rejected_unsupported",
            "failure_kind": "unsupported",
            "reason": "entry_channel=%s is explicitly unsupported" % channel,
        }
    if kind in UNSUPPORTED_SOURCE_KINDS:
        return {
            "outcome": "rejected_unsupported",
            "failure_kind": "unsupported",
            "reason": "source.kind=%s is explicitly unsupported" % kind,
        }
    if submission.get("content_type") == "文档" and channel != "飞书文档链接":
        return {
            "outcome": "rejected_unsupported",
            "failure_kind": "unsupported",
            "reason": "content_type=文档 is only supported via 飞书文档链接",
        }

    if failure_kind is not None:
        if failure_kind not in FAILURE_KINDS:
            raise ValueError("failure_kind=%r 不在取值域 %r"
                             % (failure_kind, FAILURE_KINDS))
        if failure_kind == "unsupported":
            return {
                "outcome": "rejected_unsupported",
                "failure_kind": "unsupported",
                "reason": "failure_kind=unsupported reported by caller",
            }
        return {
            "outcome": "failed",
            "failure_kind": failure_kind,
            "reason": "downstream failure: %s" % failure_kind,
        }

    return {"outcome": "accepted", "reason": "domain check passed"}


def validate_attempt(attempt):
    """逐条校验 Attempt；返回问题清单。空列表 = 合法。

    字段集合必须是 §1bis.2 的 8 个；accepted 有 ir_id / 无 failure_kind；
    其余 outcome 无 ir_id、无 receipt_id，且 failure_kind 与 outcome 对应。
    """
    p = []
    if not isinstance(attempt, dict):
        return ["attempt 必须是 dict，收到 %s" % type(attempt).__name__]

    extra = sorted(set(attempt) - set(ATTEMPT_FIELDS))
    if extra:
        p.append("出现未登记字段 %r" % (extra,))

    for key in ("attempt_id", "submission_id", "entered_at", "outcome", "reason"):
        value = attempt.get(key)
        if not isinstance(value, str) or not value.strip():
            p.append("%s 必须是非空字符串：%r" % (key, value))

    outcome = attempt.get("outcome")
    if outcome not in OUTCOMES:
        p.append("outcome=%r 不在取值域 %r" % (outcome, OUTCOMES))

    reason_problem = _reason_problem(attempt.get("reason"))
    if reason_problem:
        p.append(reason_problem)

    failure_kind = attempt.get("failure_kind")
    if outcome == "accepted":
        if "failure_kind" in attempt:
            p.append("accepted 不许带 failure_kind")
        if not isinstance(attempt.get("ir_id"), str) or not attempt.get("ir_id", "").strip():
            p.append("accepted 必须有 ir_id")
    elif outcome in ("rejected_unsupported", "failed"):
        if failure_kind not in FAILURE_KINDS:
            p.append("%s 必须有 failure_kind ∈ %r" % (outcome, FAILURE_KINDS))
        if "ir_id" in attempt:
            p.append("%s 不许有 ir_id（只有 accepted 有）" % outcome)
        if "receipt_id" in attempt:
            p.append("%s 不许有 receipt_id" % outcome)
        if outcome == "rejected_unsupported" and failure_kind != "unsupported":
            p.append("rejected_unsupported 的 failure_kind 必须是 unsupported")
        if outcome == "failed" and failure_kind == "unsupported":
            p.append("failure_kind=unsupported 必须落 rejected_unsupported，不是 failed")

    for key in ("ir_id", "receipt_id"):
        if key in attempt:
            value = attempt[key]
            if not isinstance(value, str) or not value.strip():
                p.append("%s 出现时必须是非空字符串：%r" % (key, value))
    return p


def count_outcomes(attempts):
    """按 outcome 计数；Attempt 源读不出 → AttemptReadError（不是 0）。"""
    if not isinstance(attempts, (list, tuple)):
        raise AttemptReadError("attempts 读不出：%s" % type(attempts).__name__)
    counts = {outcome: 0 for outcome in OUTCOMES}
    for i, attempt in enumerate(attempts):
        if not isinstance(attempt, dict):
            raise AttemptReadError("attempts[%d] 不是 dict" % i)
        outcome = attempt.get("outcome")
        if outcome not in counts:
            raise AttemptReadError("attempts[%d].outcome 不认识：%r" % (i, outcome))
        counts[outcome] += 1
    return counts


def count_failure_kinds(attempts):
    """四种 failure_kind 分别计数；accepted 不参与；读不出 → AttemptReadError。"""
    if not isinstance(attempts, (list, tuple)):
        raise AttemptReadError("attempts 读不出：%s" % type(attempts).__name__)
    counts = {kind: 0 for kind in FAILURE_KINDS}
    for i, attempt in enumerate(attempts):
        if not isinstance(attempt, dict):
            raise AttemptReadError("attempts[%d] 不是 dict" % i)
        if attempt.get("outcome") == "accepted":
            continue
        failure_kind = attempt.get("failure_kind")
        if failure_kind not in counts:
            raise AttemptReadError(
                "attempts[%d].failure_kind 不认识：%r" % (i, failure_kind))
        counts[failure_kind] += 1
    return counts


def check_identity(entry_count, attempts):
    """恒等式：三 outcome 之和 == 入口提交总数。返回 (ok, detail)。"""
    if not isinstance(entry_count, int) or isinstance(entry_count, bool):
        raise AttemptReadError("entry_count 读不出：%r" % (entry_count,))
    counts = count_outcomes(attempts)
    total = sum(counts.values())
    return (total == entry_count,
            "entry_count=%d attempts=%d outcomes=%r"
            % (entry_count, total, counts))


class SubmissionRouter(object):
    """入口路由器 + Attempt 唯一写者。"""

    def __init__(self, clock=None):
        self._attempts = []
        self._entry_count = 0
        self._seq = {}
        self._clock = clock or time.time

    @property
    def attempts(self):
        """只读视图：深拷贝，外部改不动内部状态。"""
        return tuple(copy.deepcopy(a) for a in self._attempts)

    @property
    def entry_count(self):
        return self._entry_count

    def submit(self, submission, *, failure_kind=None, reason=None,
               ir_id=None, receipt_id=None, now=None):
        """记录一次入口提交；返回写入的 Attempt（深拷贝）。"""
        if failure_kind is not None and failure_kind not in FAILURE_KINDS:
            raise ValueError("failure_kind=%r 不在取值域 %r"
                             % (failure_kind, FAILURE_KINDS))
        if reason is not None:
            problem = _reason_problem(reason)
            if problem:
                raise ValueError(problem)

        verdict = classify_submission(submission, failure_kind)
        outcome = verdict["outcome"]
        submission_id = submission.get("submission_id")
        if not isinstance(submission_id, str) or not submission_id.strip():
            raise ValueError("submission_id 必须是非空字符串")

        if outcome == "accepted":
            if not isinstance(ir_id, str) or not ir_id.strip():
                raise ValueError("accepted attempt 必须有 ir_id")
        else:
            if ir_id is not None:
                raise ValueError("%s 不许有 ir_id" % outcome)
            if receipt_id is not None:
                raise ValueError("%s 不许有 receipt_id" % outcome)

        entered = self._clock() if now is None else float(now)
        entered_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(entered))
        seq = self._seq.get(submission_id, 0) + 1
        self._seq[submission_id] = seq
        attempt_id = "at" + hashlib.sha256(
            ("attempt-v1|%s|%d|%s" % (submission_id, seq, entered_at))
            .encode("utf-8")).hexdigest()[:16]

        attempt = {
            "attempt_id": attempt_id,
            "submission_id": submission_id,
            "entered_at": entered_at,
            "outcome": outcome,
            "reason": reason if reason is not None else verdict["reason"],
        }
        if "failure_kind" in verdict:
            attempt["failure_kind"] = verdict["failure_kind"]
        if outcome == "accepted":
            attempt["ir_id"] = ir_id
            if receipt_id is not None:
                attempt["receipt_id"] = receipt_id

        problems = validate_attempt(attempt)
        if problems:
            raise ValueError("Attempt 不合法：\n  - " + "\n  - ".join(problems))

        self._entry_count += 1
        self._attempts.append(attempt)
        return copy.deepcopy(attempt)

    def summary(self):
        """计数与恒等式；Attempt 源读不出时抛 AttemptReadError。"""
        outcomes = count_outcomes(self._attempts)
        failure_kinds = count_failure_kinds(self._attempts)
        identity_ok, identity_detail = check_identity(
            self._entry_count, self._attempts)
        return {
            "entry_count": self._entry_count,
            "attempt_count": len(self._attempts),
            "outcomes": outcomes,
            "failure_kinds": failure_kinds,
            "identity_ok": identity_ok,
            "identity_detail": identity_detail,
        }
