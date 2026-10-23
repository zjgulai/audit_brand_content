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
  R6  source.kind=文档 的 unsupported 登记被删 → 本项红（结构性断言）
  R7  「上传文件」的 unsupported 标记被删 → 本项红（结构性断言 + 逐值循环自带清单）
  R8  四维越界值（负样本）必须被显式 rejected_unsupported
  SR-ADV3  accepted 不注入 ir_id → ValueError(「accepted attempt 必须有 ir_id」) 原文固定
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


def adv1_holds(verdict, attempt):
    """SR-ADV1：文档 + 非飞书链接必须显式 rejected_unsupported。"""
    return (verdict.get("outcome") == "rejected_unsupported"
            and verdict.get("failure_kind") == "unsupported"
            and attempt is not None
            and attempt.get("outcome") == "rejected_unsupported")


def adv2_holds(a1, a2, entry_count):
    """SR-ADV2：同 submission_id 连续两次 submit，attempt_id 必须不同。"""
    return (a1.get("attempt_id") != a2.get("attempt_id")
            and entry_count == 2)


ACCEPTED_REQUIRES_IR_MSG = "accepted attempt 必须有 ir_id"


def adv3_holds(exc, attempts_before, attempts_after):
    """SR-ADV3：accepted 不注入 ir_id → ValueError(原文) 且不落 attempt。

    变异「raise ValueError("accepted attempt 必须有 ir_id (relaxed)")」
    改的就是这一句原文。★ 消息必须**逐字相等**，不许用子串包含 ——
    `(relaxed)` 恰好**包含**原句，`in` 判据会把这次变异放过去（实测 survived）。
    """
    return (isinstance(exc, ValueError)
            and str(exc) == ACCEPTED_REQUIRES_IR_MSG
            and attempts_after == attempts_before)


# 逐值循环**自带**清单，不 enumerate 合同常量 —— 合同里删掉一个 unsupported
# 标记，检查项不会跟着消失，而是 R6/R7 的结构性断言红（变异 40/40 → 红）。
CANON_UNSUPPORTED_ENTRY_CHANNELS = ("NAS", "上传文件")


def unsupported_registration_holds(value, unsupported_coll, domain_coll):
    """R6/R7 的判据本体：`value` 必须在取值域里、且在显式 unsupported 集合里。

    拆成函数是为了 --controls 能双向喂：真合同必须判真；
    把 unsupported 集合删空 / 删项后必须判假（变异 R6/R7 的形状）。
    """
    return value in domain_coll and value in unsupported_coll


def r8_holds(verdict, attempt):
    """R8 的判据本体：一个域外样本必须**同时**在 verdict 与 attempt 两层
    落 rejected_unsupported/unsupported，缺任何一层都算没拦住。
    """
    return (verdict is not None
            and verdict.get("outcome") == "rejected_unsupported"
            and verdict.get("failure_kind") == "unsupported"
            and attempt is not None
            and attempt.get("outcome") == "rejected_unsupported")


def controls():
    """反向对照：断言对象必须真的能区分「修好」与「断开」。"""
    checks = []

    def ok(name, cond, detail=""):
        checks.append((name, bool(cond), detail))

    # SR-ADV1：把坏样本伪装成 accepted，adv1_holds 必须判假。
    bad_verdict = {"outcome": "accepted", "reason": "domain check passed"}
    bad_attempt = {"outcome": "accepted", "ir_id": "ir-bad"}
    ok("SR-ADV1 断开文档/渠道守卫 → 断言判红",
       adv1_holds(bad_verdict, bad_attempt) is False,
       "accepted 仍被判为通过")

    # SR-ADV2：两条 attempt_id 相同，adv2_holds 必须判假。
    same1 = {"attempt_id": "at-same"}
    same2 = {"attempt_id": "at-same"}
    ok("SR-ADV2 去掉序号 → 同 id 两次 → 断言判红",
       adv2_holds(same1, same2, 2) is False,
       "相同 attempt_id 仍被判为通过")

    # SR-ADV3：accepted 缺 ir_id 的异常若消息被改写，adv3_holds 必须判假。
    #   第一个坏样本只改消息（`(relaxed)` 恰好**包含**原句 —— 实测子串判据放过它）；
    #   第二个坏样本消息对、但 attempt 数变了 —— 两个维度缺一不可。
    ok("SR-ADV3 ir_id 缺失消息改写 → 断言判红",
       adv3_holds(ValueError("accepted attempt 必须有 ir_id (relaxed)"), 1, 1) is False,
       "改写后的消息仍被判为通过")
    ok("SR-ADV3 缺 ir_id 却照落 attempt → 断言判红",
       adv3_holds(ValueError("accepted attempt 必须有 ir_id"), 1, 2) is False,
       "attempt 照落仍被判为通过")

    # R6/R7 反向对照：unsupported 登记被删 → unsupported_registration_holds 判假。
    ok("R6 删掉 source.kind=文档 的 unsupported 登记 → 断言判红",
       unsupported_registration_holds("文档", (), C.SOURCE_KIND_DOMAIN) is False,
       "不在 unsupported 集合仍被判为通过")
    ok("R7 删掉「上传文件」的 unsupported 标记 → 断言判红",
       unsupported_registration_holds("上传文件", ("NAS",), C.ENTRY_CHANNELS) is False,
       "不在 unsupported 集合仍被判为通过")

    # R8 反向对照：越界值被放行（accepted / attempt 缺失）→ r8_holds 必须判假。
    ok("R8 域外值被判 accepted → 断言判红",
       r8_holds({"outcome": "accepted", "reason": "domain check passed"},
                {"outcome": "accepted"}) is False,
       "越界值仍被判为通过")
    ok("R8 attempt 层缺失 → 断言判红",
       r8_holds({"outcome": "rejected_unsupported", "failure_kind": "unsupported"},
                None) is False,
       "attempt 层缺失仍被判为通过")

    # 正样本：真实实现必须能过（不是恒红）。
    r = SR.SubmissionRouter()
    sub = {
        "submission_id": "control-doc",
        "content_type": "文档",
        "content_stage": "brief",
        "entry_channel": "群消息",
        "source": {"kind": "free_text"},
    }
    v = SR.classify_submission(sub)
    try:
        a = r.submit(sub)
    except Exception as exc:  # noqa: BLE001
        a = {"outcome": "exception:%s" % type(exc).__name__}
    ok("SR-ADV1 真实实现 → 断言判绿", adv1_holds(v, a), "verdict=%r attempt=%r" % (v, a))

    r2 = SR.SubmissionRouter()
    base = {
        "submission_id": "control-retry",
        "content_type": "文本",
        "content_stage": "brief",
        "entry_channel": "群消息",
        "source": {"kind": "free_text"},
    }
    x1 = r2.submit(base, ir_id="ir-1", now=1000)
    x2 = r2.submit(base, ir_id="ir-2", now=1000)
    r3 = SR.SubmissionRouter()
    try:
        r3.submit(base, now=1000)
        err_ir = None
    except Exception as exc:  # noqa: BLE001
        err_ir = exc
    ok("SR-ADV2 真实实现 → 断言判绿", adv2_holds(x1, x2, r2.entry_count),
       "%s vs %s entry=%d" % (x1["attempt_id"], x2["attempt_id"], r2.entry_count))

    ok("SR-ADV3 真实实现 → 断言判绿", adv3_holds(err_ir, 1, 1),
       "err=%r before=1 after=%d" % (err_ir, len(r3.attempts)))

    ok("R6/R7 真实合同 → 断言判绿",
       unsupported_registration_holds("文档", SR.UNSUPPORTED_SOURCE_KINDS,
                                      SR.SOURCE_KIND_DOMAIN)
       and unsupported_registration_holds("上传文件",
                                          SR.UNSUPPORTED_ENTRY_CHANNELS,
                                          SR.ENTRY_CHANNEL_DOMAIN),
       "SR.UNSUPPORTED_SOURCE_KINDS=%r SR.UNSUPPORTED_ENTRY_CHANNELS=%r"
       % (tuple(SR.UNSUPPORTED_SOURCE_KINDS), tuple(SR.UNSUPPORTED_ENTRY_CHANNELS)))

    failed = [c for c in checks if not c[1]]
    for name, good, detail in checks:
        print("%s %s%s" % ("✓" if good else "✗", name,
                           "" if good else " —— " + detail))
    print("\n%s %d/%d 项通过"
          % ("✅" if not failed else "❌", len(checks) - len(failed), len(checks)))
    return 0 if not failed else 1


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

    # R8 反面样本：四个维度各一个**域外值**，必须被显式 rejected_unsupported，
    # 不得静默成功。缺了这一组，「把某维校验项从 _entry_problems 删掉」的变异
    # 会让所有正样本照常 accepted —— 假绿（实测 40/40）。
    oob = [
        ("content_type", "音频"),
        ("content_stage", "review"),
        ("entry_channel", "邮件"),
        ("source.kind", None),   # 特判：source 不是 dict → kind=None 不在域内
    ]
    r_oob = new_router()
    oob_bad = []
    for j, (field, val) in enumerate(oob):
        if field == "source.kind":
            sub = base_sub(submission_id="oob-%d" % j, source="not-a-dict")
        else:
            sub = base_sub(submission_id="oob-%d" % j, **{field: val})
        verdict = SR.classify_submission(sub)
        try:
            # 域外值注定 rejected_unsupported：不传 ir_id（rejected 不许带）。
            a_oob = r_oob.submit(sub)
        except Exception:  # noqa: BLE001
            # 落异常同样不是 rejected_unsupported（例如守卫被删后走 accepted
            # 分支又缺 ir_id）—— 两个方向都算红。
            a_oob = None
        if not r8_holds(verdict, a_oob):
            oob_bad.append((field, val, verdict, a_oob))
    report(not oob_bad, "R8 四维域外值 → rejected_unsupported（不得静默成功）",
           repr(oob_bad[:1]))

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
    # ★ 逐值循环自带清单（不 enumerate C.UNSUPPORTED_ENTRY_CHANNELS）：
    #   合同里的标记集合被删项时，检查项不会跟着消失（那是变异 3 的假绿形状），
    #   而是下面 R7 的集合恒等断言红。
    for i, ch in enumerate(CANON_UNSUPPORTED_ENTRY_CHANNELS):
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

    # R1/R6/R7 结构性反向对照：unsupported 登记必须双向对齐（判据在
    # unsupported_registration_holds，--controls 双向喂过它）。
    report(unsupported_registration_holds(
               "NAS", SR.UNSUPPORTED_ENTRY_CHANNELS, SR.ENTRY_CHANNEL_DOMAIN)
           and unsupported_registration_holds(
               "上传文件", SR.UNSUPPORTED_ENTRY_CHANNELS, SR.ENTRY_CHANNEL_DOMAIN),
           "R7 删掉 unsupported 入口标记 → 本项红",
           "domain=%r unsupported=%r"
           % (tuple(SR.ENTRY_CHANNEL_DOMAIN), tuple(SR.UNSUPPORTED_ENTRY_CHANNELS)))
    report(unsupported_registration_holds(
               "文档", SR.UNSUPPORTED_SOURCE_KINDS, SR.SOURCE_KIND_DOMAIN),
           "R6 删掉 source.kind=文档 的 unsupported 登记 → 本项红",
           "domain=%r unsupported=%r"
           % (tuple(SR.SOURCE_KIND_DOMAIN), tuple(SR.UNSUPPORTED_SOURCE_KINDS)))

    # SR-ADV1：content_type=文档 只有飞书文档链接合法；群消息必须显式拒绝
    sub_doc = base_sub(submission_id="doc-wrong-channel",
                       content_type="文档", entry_channel="群消息",
                       source={"kind": "free_text"})
    verdict_doc = SR.classify_submission(sub_doc)
    try:
        # 不传 ir_id：正常路径必须落 rejected_unsupported；若守卫被删，
        # classify_submission 会先返回 accepted，下面的 verdict 断言就会红。
        a_doc = r.submit(sub_doc)
        err_doc = None
    except Exception as exc:  # noqa: BLE001
        a_doc, err_doc = None, exc
    report(adv1_holds(verdict_doc, a_doc),
           "SR-ADV1 content_type=文档 + 群消息 → rejected_unsupported",
           "verdict=%r attempt=%r err=%r" % (verdict_doc, a_doc, err_doc))

    # SR-ADV3：supported 四维 + accepted，但调用方**不注入 ir_id**。
    #   正常路径必须 raise ValueError("accepted attempt 必须有 ir_id") 且不落 attempt。
    #   变异「…ir_id (relaxed)」改掉消息原文后，本项红（adv3_holds 判假）。
    r_adv3 = new_router()
    n_before = len(r_adv3.attempts)
    try:
        r_adv3.submit(base_sub(submission_id="adv3-no-ir"))
        err_no_ir = None
    except Exception as exc:  # noqa: BLE001
        err_no_ir = exc
    report(adv3_holds(err_no_ir, n_before, len(r_adv3.attempts)),
           "SR-ADV3 accepted 不注入 ir_id → ValueError 原文固定且不落 attempt",
           "err=%r attempts=%d" % (err_no_ir, len(r_adv3.attempts)))

    # C4 source.kind：六类 accepted；文档 unsupported
    r = new_router()
    bad = []
    for i, kind in enumerate(C.SOURCE_KINDS):
        a = r.submit(base_sub(submission_id="sk-%d" % i,
                              source={"kind": kind}), ir_id="ir-sk-%d" % i)
        if a.get("outcome") != "accepted":
            bad.append((kind, a))
    report(not bad, "C4 六类 source.kind accepted", repr(bad[:1]))
    # ★ C4 反面（R6 行为面）：source.kind=文档 必须落 rejected_unsupported。
    #   不把 submit 的异常裸抛 —— 变异 2 的形状（登记删空 → 文档走 accepted
    #   分支）必须落在本项红上，而不是让验收器崩掉（崩 ≠ 抓住）。
    a = None
    try:
        a = r.submit(base_sub(submission_id="sk-doc", source={"kind": "文档"}))
        err = None
    except Exception as exc:  # noqa: BLE001
        err = exc
    report(a is not None
           and a.get("outcome") == "rejected_unsupported"
           and a.get("failure_kind") == "unsupported"
           and "ir_id" not in a,
           "C4 source.kind=文档 → rejected_unsupported",
           "attempt=%r err=%r" % (a, err))

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
    r.submit(base_sub(submission_id="ir-relaxed"), ir_id="ir-relaxed")
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
    report(adv2_holds(a1, a2, r.entry_count),
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
        if "--controls" in sys.argv:
            sys.exit(controls())
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 验收器自身异常: %s" % exc)
        sys.exit(2)
