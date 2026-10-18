#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_submission_router.py — T1-01：submission_router + Attempt

覆盖：
  C0  四维取值域来自 base/contract.py（5/2/6/7）
  C1  content_type 5 值逐个 accepted
  C2  content_stage 2 值逐个 accepted
  C3  entry_channel：前四条 accepted；NAS / 上传文件显式 rejected_unsupported
  C4  source.kind：六类 accepted；文档 rejected_unsupported
  C5  Attempt 字段集合 / 必填 / 互斥字段（accepted 有 ir_id；unsupported 无 ir_id）
  C6  四种 failure_kind 可分别计数；全 0 时四个键仍存在
  C7  Attempt 读不出 → AttemptReadError（未测，不是 0）
  C8  Attempt 唯一写者：attempts 是只读副本，只能由 submit 追加
  C9  恒等式：accepted + rejected_unsupported + failed == 入口提交总数
  R1  删掉 NAS 取值 → 本项红（结构性断言）
  R2  unsupported 被静默成功 → 本项红（行为断言）
  R3  漏记一条 attempt → 恒等式红
  R4  reason 写「其他」「未知错误」→ 红
  R5  其它非法 Attempt（缺字段/多字段/互斥字段）→ 红
  S1  若 contracts/attempt-v1.schema.json 已落盘，字段集合必须一致

退出码：0 全过 / 1 有红 / 2 未测（导入失败或验收器自身异常）。
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

try:
    from base import contract as C
    from base import submission_router as SR
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 base.contract / base.submission_router: %s" % exc)
    sys.exit(2)


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

    def base_sub(**over):
        s = {
            "submission_id": "sub-1",
            "content_type": "文本",
            "content_stage": "brief",
            "entry_channel": "群消息",
            "source": {"kind": "free_text"},
        }
        s.update(over)
        return s

    def new_router():
        return SR.SubmissionRouter()

    # C0 四维取值域来自 contract.py
    report(SR.CONTENT_TYPES == C.CONTENT_TYPES
           and len(SR.CONTENT_TYPES) == 5,
           "C0 content_type 5 值来自 contract.py", repr(SR.CONTENT_TYPES))
    report(SR.CONTENT_STAGES == C.CONTENT_STAGES
           and len(SR.CONTENT_STAGES) == 2,
           "C0 content_stage 2 值来自 contract.py", repr(SR.CONTENT_STAGES))
    report(SR.ENTRY_CHANNEL_DOMAIN == C.ENTRY_CHANNELS
           and len(SR.ENTRY_CHANNEL_DOMAIN) == 6,
           "C0 entry_channel 6 值来自 contract.py", repr(SR.ENTRY_CHANNEL_DOMAIN))
    report(SR.SOURCE_KIND_DOMAIN == C.SOURCE_KIND_DOMAIN
           and len(SR.SOURCE_KIND_DOMAIN) == 7,
           "C0 source.kind 7 值来自 contract.py", repr(SR.SOURCE_KIND_DOMAIN))

    # C1 content_type 逐个 accepted
    ct_kind = {
        "文本": "free_text", "图片": "image", "视频": "video",
        "文档": "free_text", "结构化记录": "structured_json",
    }
    r = new_router()
    bad = []
    for i, ct in enumerate(C.CONTENT_TYPES):
        a = r.submit(base_sub(
            submission_id="ct-%d" % i,
            content_type=ct,
            entry_channel=("飞书文档链接" if ct == "文档" else "群消息"),
            source={"kind": ct_kind[ct]}), ir_id="ir-ct-%d" % i)
        if a.get("outcome") != "accepted" or SR.validate_attempt(a):
            bad.append((ct, a))
    report(not bad, "C1 content_type 5 值逐个 accepted", repr(bad[:1]))

    # C2 content_stage 逐个 accepted
    r = new_router()
    bad = []
    for i, stage in enumerate(C.CONTENT_STAGES):
        a = r.submit(base_sub(submission_id="cs-%d" % i,
                              content_stage=stage), ir_id="ir-cs-%d" % i)
        if a.get("outcome") != "accepted":
            bad.append((stage, a))
    report(not bad, "C2 content_stage 2 值逐个 accepted", repr(bad[:1]))

    # C3 entry_channel：前四条 accepted，NAS/上传文件显式 unsupported
    r = new_router()
    supported = ["群消息", "飞书文档链接", "落地页 URL", "多维表批量"]
    bad = []
    for i, ch in enumerate(supported):
        a = r.submit(base_sub(submission_id="ch-%d" % i,
                              entry_channel=ch), ir_id="ir-ch-%d" % i)
        if a.get("outcome") != "accepted":
            bad.append((ch, a))
    report(not bad, "C3 前四条入口通道 accepted", repr(bad[:1]))
    for i, ch in enumerate(C.UNSUPPORTED_ENTRY_CHANNELS):
        sub = base_sub(submission_id="ch-u-%d" % i, entry_channel=ch)
        verdict = SR.classify_submission(sub)
        try:
            a = r.submit(sub)
            err = None
        except Exception as exc:  # noqa: BLE001
            a, err = None, exc
        report(
            verdict.get("outcome") == "rejected_unsupported"
            and verdict.get("failure_kind") == "unsupported"
            and ch in verdict.get("reason", "")
            and "explicitly unsupported" in verdict.get("reason", "")
            and a is not None
            and a.get("outcome") == "rejected_unsupported"
            and a.get("failure_kind") == "unsupported"
            and "ir_id" not in a and "receipt_id" not in a,
            "R1/R2 %s → rejected_unsupported（显式，不得静默成功）" % ch,
            "verdict=%r attempt=%r err=%r" % (verdict, a, err))

    # R1 结构性反向对照：NAS 必须仍在取值域与 unsupported 集合里
    report("NAS" in SR.ENTRY_CHANNEL_DOMAIN
           and "NAS" in C.ENTRY_CHANNELS
           and "NAS" in SR.UNSUPPORTED_ENTRY_CHANNELS,
           "R1 删掉 NAS 取值 → 本项红", repr(SR.ENTRY_CHANNEL_DOMAIN))

    # SR-ADV1：content_type=文档 只有飞书文档链接合法；群消息必须显式拒绝
    sub_doc = base_sub(submission_id="doc-wrong-channel",
                       content_type="文档", entry_channel="群消息",
                       source={"kind": "free_text"})
    verdict_doc = SR.classify_submission(sub_doc)
    try:
        a_doc = r.submit(sub_doc)
        err_doc = None
    except Exception as exc:  # noqa: BLE001
        a_doc, err_doc = None, exc
    report(verdict_doc.get("outcome") == "rejected_unsupported"
           and verdict_doc.get("failure_kind") == "unsupported"
           and a_doc is not None
           and a_doc.get("outcome") == "rejected_unsupported",
           "SR-ADV1 content_type=文档 + 群消息 → rejected_unsupported",
           "verdict=%r attempt=%r err=%r" % (verdict_doc, a_doc, err_doc))

    # C4 source.kind：六类 accepted；文档 unsupported
    r = new_router()
    bad = []
    for i, kind in enumerate(C.SOURCE_KINDS):
        a = r.submit(base_sub(submission_id="sk-%d" % i,
                              source={"kind": kind}), ir_id="ir-sk-%d" % i)
        if a.get("outcome") != "accepted":
            bad.append((kind, a))
    report(not bad, "C4 六类 source.kind accepted", repr(bad[:1]))
    a = r.submit(base_sub(submission_id="sk-doc", source={"kind": "文档"}))
    report(a.get("outcome") == "rejected_unsupported"
           and a.get("failure_kind") == "unsupported"
           and "ir_id" not in a,
           "C4 source.kind=文档 → rejected_unsupported", repr(a))

    # C5 Attempt 字段集合
    expected_fields = ("attempt_id", "submission_id", "entered_at", "outcome",
                       "failure_kind", "reason", "ir_id", "receipt_id")
    report(tuple(SR.ATTEMPT_FIELDS) == expected_fields,
           "C5 Attempt 字段集合与 §1bis.2 一致", repr(SR.ATTEMPT_FIELDS))
    all_attempts = r.attempts
    report(all(isinstance(a, dict) and set(a) <= set(expected_fields)
               for a in all_attempts),
           "C5 每条 Attempt 只含已登记字段", "")

    good = {
        "attempt_id": "at1", "submission_id": "s1",
        "entered_at": "2026-10-18T00:00:00Z",
        "outcome": "accepted", "reason": "domain check passed",
        "ir_id": "ir1",
    }
    report(SR.validate_attempt(good) == [],
           "C5 合法 accepted Attempt 通过", repr(SR.validate_attempt(good)))
    report(SR.validate_attempt({
        "attempt_id": "at2", "submission_id": "s2",
        "entered_at": "2026-10-18T00:00:00Z",
        "outcome": "rejected_unsupported", "failure_kind": "unsupported",
        "reason": "entry_channel=NAS is explicitly unsupported"}) == [],
        "C5 合法 rejected_unsupported Attempt 通过", "")
    report(SR.validate_attempt({
        "attempt_id": "at3", "submission_id": "s3",
        "entered_at": "2026-10-18T00:00:00Z",
        "outcome": "failed", "failure_kind": "parse_error",
        "reason": "downstream parse_error"}) == [],
        "C5 合法 failed Attempt 通过", "")

    negatives = [
        ("缺 attempt_id", {k: v for k, v in good.items() if k != "attempt_id"}),
        ("多一个字段", {**good, "extra": 1}),
        ("accepted 缺 ir_id", {k: v for k, v in good.items() if k != "ir_id"}),
        ("accepted 带 failure_kind", {**good, "failure_kind": "parse_error"}),
        ("rejected 带 ir_id", {
            "attempt_id": "at4", "submission_id": "s4",
            "entered_at": "2026-10-18T00:00:00Z",
            "outcome": "rejected_unsupported", "failure_kind": "unsupported",
            "reason": "NAS explicitly unsupported", "ir_id": "ir4"}),
        ("rejected 带 receipt_id", {
            "attempt_id": "at5", "submission_id": "s5",
            "entered_at": "2026-10-18T00:00:00Z",
            "outcome": "rejected_unsupported", "failure_kind": "unsupported",
            "reason": "NAS explicitly unsupported", "receipt_id": "r5"}),
        ("failed 用 unsupported", {
            "attempt_id": "at6", "submission_id": "s6",
            "entered_at": "2026-10-18T00:00:00Z",
            "outcome": "failed", "failure_kind": "unsupported",
            "reason": "should be rejected_unsupported"}),
        ("reason=其他", {**good, "reason": "其他"}),
        ("reason=未知错误", {**good, "reason": "未知错误"}),
        ("reason 为空", {**good, "reason": "  "}),
    ]
    for name, bad_attempt in negatives:
        report(bool(SR.validate_attempt(bad_attempt)),
               "R4/R5 %s → 红" % name, repr(SR.validate_attempt(bad_attempt)))

    # C6 四种 failure_kind 可分别计数
    r = new_router()
    for i, fk in enumerate(("fetch_error", "parse_error", "empty")):
        r.submit(base_sub(submission_id="fk-%d" % i),
                 failure_kind=fk, reason="downstream %s" % fk)
    try:
        r.submit(base_sub(submission_id="fk-u", entry_channel="NAS"))
    except Exception as exc:  # noqa: BLE001
        report(False, "C6 unsupported attempt 必须可写入", repr(exc))
    counts = SR.count_failure_kinds(r.attempts)
    report(set(counts) == set(C.FAILURE_KINDS)
           and all(counts[k] >= 1 for k in C.FAILURE_KINDS),
           "C6 四种 failure_kind 分别计数", repr(counts))

    r2 = new_router()
    r2.submit(base_sub(submission_id="only-ok"), ir_id="ir-only")
    zero = SR.count_failure_kinds(r2.attempts)
    report(set(zero) == set(C.FAILURE_KINDS)
           and all(v == 0 for v in zero.values()),
           "C6 全 0 时四个键仍存在（未测 ≠ 0 另测）", repr(zero))

    # C7 读不出 → AttemptReadError，不是 0
    for fn, args, name in (
            (SR.count_outcomes, (None,), "count_outcomes(None)"),
            (SR.count_failure_kinds, (None,), "count_failure_kinds(None)"),
            (SR.check_identity, (1, None), "check_identity(1, None)")):
        try:
            fn(*args)
            ok = False
        except SR.AttemptReadError:
            ok = True
        report(ok, "C7 %s → AttemptReadError（未测，不是 0）" % name, "")

    # C8 唯一写者：attempts 是只读副本
    r = new_router()
    r.submit(base_sub(submission_id="solo"), ir_id="ir-solo")
    snap = r.attempts
    report(isinstance(snap, tuple), "C8 attempts 是只读 tuple", repr(type(snap)))
    if snap:
        before = r.summary()["outcomes"]
        snap[0]["outcome"] = "failed"
        report(r.summary()["outcomes"] == before,
               "C8 改副本不改内部状态（唯一写者是 submit）", "")

    # SR-ADV2 同一 submission_id / 同一时刻重试：attempt_id 必须不同
    r = new_router()
    a1 = r.submit(base_sub(submission_id="retry-same"), ir_id="ir-r1", now=1000)
    a2 = r.submit(base_sub(submission_id="retry-same"), ir_id="ir-r2", now=1000)
    report(a1["attempt_id"] != a2["attempt_id"] and r.entry_count == 2,
           "SR-ADV2 同 submission_id/同 now 重试 → attempt_id 不同",
           "%s vs %s entry=%d"
           % (a1["attempt_id"], a2["attempt_id"], r.entry_count))

    # C9 恒等式
    r = new_router()
    r.submit(base_sub(submission_id="id-a"), ir_id="ir-a")
    try:
        r.submit(base_sub(submission_id="id-b", entry_channel="NAS"))
    except Exception as exc:  # noqa: BLE001
        report(False, "C9 unsupported attempt 必须可写入", repr(exc))
    r.submit(base_sub(submission_id="id-c"), failure_kind="parse_error",
             reason="downstream parse_error")
    summary = r.summary()
    report(summary["identity_ok"] is True
           and sum(summary["outcomes"].values()) == summary["entry_count"],
           "C9 accepted + rejected + failed == 入口总数",
           repr(summary))
    ok_missing, detail_missing = SR.check_identity(
        summary["entry_count"], r.attempts[:-1])
    report(ok_missing is False,
           "R3 漏记一条 attempt → 恒等式红", detail_missing)
    ok_extra, detail_extra = SR.check_identity(
        summary["entry_count"] + 1, r.attempts)
    report(ok_extra is False,
           "C9 多算一条入口 → 恒等式红", detail_extra)

    # S1 schema 若已落盘，字段集合必须一致
    schema_path = os.path.join(REPO_ROOT, "contracts", "attempt-v1.schema.json")
    if os.path.exists(schema_path):
        try:
            import json
            schema = json.loads(open(schema_path, encoding="utf-8").read())
            props = set((schema.get("properties") or {}).keys())
            req = set(schema.get("required") or [])
            report(props == set(expected_fields)
                   and req <= set(expected_fields)
                   and {"attempt_id", "submission_id", "entered_at",
                        "outcome", "reason"} <= req,
                   "S1 attempt-v1.schema.json 字段集合一致",
                   "props=%r required=%r" % (sorted(props), sorted(req)))
        except Exception as exc:  # noqa: BLE001
            report(False, "S1 attempt-v1.schema.json 可解析", repr(exc))
    else:
        print("SKIP: contracts/attempt-v1.schema.json 尚未落盘（0e 在产）")

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
