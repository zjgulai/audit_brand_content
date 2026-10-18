#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_release_gate.py —— `base/release_gate.py` 的判据（T2-03 / RL-1…RL-15）

## 它验什么

  A **状态机**：pending_release → signed / rejected；signed → revoked；
    signed → invalidated →（重审完成后）pending_release；非法迁移必须拒。
  B **签发绑定全字段**：case_version / IR id+version / raw+text / rule+kb 快照
    （version+hash）/ used_authority_refs / conflict_table_version / 六类媒体指纹 +
    root hash / signature_version；缺一或签名被改 → 红。
  C **SoD**：提交人、最终复核人不可签；跨租户/品线/无 release.sign → 拒。
  D **step-up**：必须消费；重复使用、错误 action/nonce、过期 → 拒（接 auth_session）。
  E **失效五类**：content / rule_snapshot / kb_snapshot / used ref versions /
    conflict_table_version；**未使用的 ref 变化不触发**（SB-8）。
  F **重审 job**：invalidated 必须自动建 job；queued 合并 change_set；running 时新建
    successor；同 change_set 幂等；完成后回 pending_release。
  G **机器不可写放行**：任何 patch 带 release_status → 拒。
  H **签名不可变**：旧签名被改 → validate 红；重新签发 = 新记录 + derived_from。

## 退出码

  0 全过 · 1 有红 · 2 未测（导入失败之外的不可测条件）
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "base"))
sys.path.insert(0, ROOT)

try:
    from auth_session import SessionStore
    from release_gate import (
        ReleaseGate, SIGNATURE_FIELDS, SignatureError, StepUpError,
        SoDViolation, InvalidTransition, MachineWriteDenied, media_root,
        validate_signature)
except Exception as e:  # noqa: BLE001
    print("❌ 导入 base/release_gate.py / auth_session 失败：%s" % e)
    sys.exit(1)


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


MEDIA = [
    {"kind": "image", "stable_id": "k1", "sha256": "a" * 64},
    {"kind": "image", "stable_id": "k0", "sha256": "b" * 64},
]


def case(**over):
    c = {
        "case_id": "case-1", "case_version": 3,
        "ir_id": "ir-1", "ir_version": "review-ir-v1",
        "raw_sha256": "1" * 64, "text_sha256": "2" * 64,
        "rule_snapshot": {"version": "rs-1", "hash": "3" * 64},
        "kb_snapshot": {"version": "kb-1", "hash": "4" * 64},
        "used_authority_refs": [{"ref_id": "E1", "version": "v1"},
                                {"ref_id": "E2", "version": "v1"}],
        "conflict_table_version": "ct-1",
        "media_fingerprints": list(MEDIA),
        "frame_manifest_hash": "f" * 64, "keyframe_set_hash": "e" * 64,
        "ocr_output_hash": "d" * 64, "asr_output_hash": "c" * 64,
        "model_config_hash": "b" * 64, "sampling_config_hash": "a" * 64,
        "submitter_id": "u1", "final_reviewer_id": "u2",
        "tenant": "t1", "product_line": "p1",
        "release_status": "待放行",
    }
    c.update(over)
    return c


def signer(uid="u3", **over):
    p = {"id": uid, "tenant": "t1", "product_line": "p1",
         "roles": ["signer"], "capabilities": ["release.sign", "release.revoke"]}
    p.update(over)
    return p


def main():
    fails = []
    checks = 0
    try:
        TMP = tempfile.mkdtemp(prefix="releasegate_")
    except OSError as e:
        print("⚠ 未测：建不出临时目录（%s）" % e)
        return 2

    def T(cid, ok, detail=""):
        nonlocal checks
        checks += 1
        if not ok:
            fails.append("%s  %s" % (cid, detail))

    def new_gate(tag):
        sessions = SessionStore(os.path.join(TMP, "sess_%s.db" % tag))
        return ReleaseGate(sessions=sessions), sessions

    def token(sessions, p, c, action="sign", nonce="n1", now=1000):
        return sessions.issue_step_up(p["id"], c["case_id"], action, nonce, now=now)

    # ── A 状态机 ────────────────────────────────────────────────────
    gate, sess = new_gate("a")
    c = case()
    s = signer()
    tk = token(sess, s, c)
    sig = gate.sign(c, s, tk, "n1", reason="人工复核通过", now=1001)
    st = gate.state("case-1")
    T("A1 sign → signed / 已放行",
      st["status"] == "signed" and st["release_status"] == "已放行", str(st))
    T("A2 pending 列表不再含该案", gate.pending() == [], str(gate.pending()))
    try:
        gate.sign(c, s, token(sess, s, c, nonce="n2"), "n2", reason="test", now=1002)
        T("A3 已放行再次 sign → 拒", False, "未拒")
    except InvalidTransition:
        T("A3 已放行再次 sign → 拒", True, "")

    gate2, sess2 = new_gate("a2")
    c2 = case(case_id="case-2")
    tk2 = token(sess2, s, c2, action="reject", nonce="r1")
    gate2.reject(c2, s, tk2, "r1", reason="证据不足", now=1001)
    T("A4 reject → rejected / 已拒绝",
      gate2.state("case-2")["status"] == "rejected"
      and gate2.state("case-2")["release_status"] == "已拒绝", str(gate2.state("case-2")))
    try:
        gate2.revoke(c2, s, "x", "x", reason="x")
        T("A5 rejected 不能 revoke", False, "未拒")
    except InvalidTransition:
        T("A5 rejected 不能 revoke", True, "")

    gate3, sess3 = new_gate("a3")
    c3 = case(case_id="case-3")
    tk3 = token(sess3, s, c3, nonce="s3")
    gate3.sign(c3, s, tk3, "s3", reason="test", now=1001)
    tk3r = token(sess3, s, c3, action="revoke", nonce="rv3")
    gate3.revoke(c3, s, tk3r, "rv3", reason="内容修改", now=1002)
    T("A6 signed → revoked / 已撤回",
      gate3.state("case-3")["status"] == "revoked"
      and gate3.state("case-3")["release_status"] == "已撤回", str(gate3.state("case-3")))

    # ── B 签发绑定全字段 ────────────────────────────────────────────
    T("B1 签名包含全部绑定字段", set(SIGNATURE_FIELDS) <= set(sig), str(sorted(set(SIGNATURE_FIELDS) - set(sig))))
    T("B2 validate_signature 对真签名零错误", validate_signature(sig) == [], str(validate_signature(sig)))
    for field in ("case_version", "ir_id", "raw_sha256", "rule_snapshot_hash",
                  "used_authority_refs", "conflict_table_version",
                  "media_fingerprints_root_hash", "signature_version"):
        bad = dict(sig)
        bad.pop(field, None)
        T("B3 删绑定字段 %s → 红" % field, validate_signature(bad) != [], "")
    bad = dict(sig, case_version=99)
    T("B4 改 case_version → 签名哈希不符", validate_signature(bad) != [], "")
    bad = dict(sig, media_fingerprints_root_hash="0" * 64)
    T("B5 改 media root → 红", validate_signature(bad) != [], "")
    T("B6 media root 与顺序无关",
      media_root(MEDIA) == media_root(list(reversed(MEDIA))), "")
    miss = case()
    miss.pop("rule_snapshot")
    try:
        gx, sx = new_gate("bmiss")
        tk = token(sx, s, miss)
        gx.sign(miss, s, tk, "n1", reason="test", now=1001)
        T("B7 case 缺 rule_snapshot → 签发拒", False, "未拒")
    except SignatureError:
        T("B7 case 缺 rule_snapshot → 签发拒", True, "")

    # ── C SoD ───────────────────────────────────────────────────────
    def must_deny(cid, fn, exc=Exception):
        try:
            fn()
            T(cid, False, "未拒")
        except exc:
            T(cid, True, "")
        except Exception as e:  # 非预期异常也必须记 FAIL，不许 traceback 顶穿
            T(cid, False, "非预期异常 %s: %s" % (type(e).__name__, e))

    g4, s4 = new_gate("c")
    c4 = case(case_id="case-4")
    must_deny("C1 提交人自签 → 拒",
              lambda: g4.sign(c4, signer("u1"), token(s4, signer("u1"), c4), "n1", reason="test", now=1001),
              SoDViolation)
    must_deny("C2 最终复核人自签 → 拒",
              lambda: g4.sign(c4, signer("u2"), token(s4, signer("u2"), c4), "n1", reason="test", now=1001),
              SoDViolation)
    must_deny("C3 跨租户 → 拒",
              lambda: g4.sign(c4, signer("u3", tenant="t2"), token(s4, signer("u3", tenant="t2"), c4), "n1", reason="test", now=1001),
              SoDViolation)
    must_deny("C4 跨品线 → 拒",
              lambda: g4.sign(c4, signer("u3", product_line="p2"), token(s4, signer("u3", product_line="p2"), c4), "n1", reason="test", now=1001),
              SoDViolation)
    must_deny("C5 无 release.sign → 拒",
              lambda: g4.sign(c4, signer("u3", capabilities=[]), token(s4, signer("u3", capabilities=[]), c4), "n1", reason="test", now=1001),
              SoDViolation)

    # ── D step-up ───────────────────────────────────────────────────
    g5, s5 = new_gate("d")
    c5 = case(case_id="case-5")
    tk5 = token(s5, s, c5, nonce="d1")
    g5.sign(c5, s, tk5, "d1", reason="test", now=1001)
    must_deny("D1 同一 step-up 二次使用 → 拒",
              lambda: g5.sign(case(case_id="case-5b"), s, tk5, "d1", reason="test", now=1002),
              StepUpError)
    g6, s6 = new_gate("d2")
    c6 = case(case_id="case-6")
    tk_wrong = token(s6, s, c6, nonce="right")
    must_deny("D2 错误 nonce → 拒",
              lambda: g6.sign(c6, s, tk_wrong, "wrong", reason="test", now=1001), StepUpError)
    tk_old = token(s6, s, c6, nonce="old", now=1000)
    must_deny("D3 过期 step-up → 拒",
              lambda: g6.sign(c6, s, tk_old, "old", reason="test", now=2000), StepUpError)
    must_deny("D4 错误 action → 拒",
              lambda: g6.sign(c6, s, token(s6, s, c6, action="reject", nonce="act"), "act", reason="test", now=1001),
              StepUpError)
    g7, _ = new_gate("d3")
    must_deny("D5 没有 session store → 拒（不许绕过）",
              lambda: ReleaseGate(sessions=None).sign(case(case_id="case-7"), s, "x", "n", reason="test", now=1001),
              StepUpError)

    # ── E 失效五类 ─────────────────────────────────────────────────
    def signed_case(tag):
        g, ss = new_gate(tag)
        cc = case(case_id="case-" + tag)
        tk = token(ss, s, cc, nonce="n" + tag)
        g.sign(cc, s, tk, "n" + tag, reason="test", now=1001)
        return g, ss, cc

    for cid, mutate, field in (
        ("E1 内容指纹变化", lambda x: x.update(raw_sha256="9" * 64), "raw_sha256"),
        ("E2 rule_snapshot 变化", lambda x: x.update(rule_snapshot={"version": "rs-2", "hash": "9" * 64}), "rule_snapshot"),
        ("E3 kb_snapshot 变化", lambda x: x.update(kb_snapshot={"version": "kb-2", "hash": "9" * 64}), "kb_snapshot"),
        ("E4 used ref 版本变化", lambda x: x.update(used_authority_refs=[{"ref_id": "E1", "version": "v2"}, {"ref_id": "E2", "version": "v1"}]), "used_authority_refs"),
        ("E5 conflict table 变化", lambda x: x.update(conflict_table_version="ct-2"), "conflict_table_version"),
    ):
        g, ss, cc = signed_case(cid.split()[0])
        cur = case(case_id=cc["case_id"])
        mutate(cur)
        res = g.invalidate(cc["case_id"], cur, now=1002)
        T(cid + " → invalidated", res.get("invalidated") is True
          and any(x["field"] == field for x in res.get("change_set", [])), str(res))
        T(cid + " → 自动建 queued job", res.get("job") is not None
          and res["job"]["state"] == "queued", str(res.get("job")))

    g8, s8, c8 = signed_case("e8")
    cur = case(case_id=c8["case_id"],
               used_authority_refs=[{"ref_id": "E1", "version": "v1"},
                                    {"ref_id": "E2", "version": "v1"},
                                    {"ref_id": "UNUSED", "version": "v9"}])
    res = g8.invalidate(c8["case_id"], cur, now=1002)
    T("E6 未使用 ref 变化/新增 → 不失效（SB-8）", res.get("invalidated") is False, str(res))
    g9, s9, c9 = signed_case("e9")
    cur = case(case_id=c9["case_id"],
               used_authority_refs=[{"ref_id": "E1", "version": "v9"},
                                    {"ref_id": "E2", "version": "v9"}])
    T("E7 使用中的 ref 版本变化 → 失效",
      g9.invalidate(c9["case_id"], cur, now=1002).get("invalidated") is True, "")

    # ── F 重审 job ──────────────────────────────────────────────────
    g10, s10, c10 = signed_case("f10")
    cur1 = case(case_id=c10["case_id"], raw_sha256="9" * 64)
    r1 = g10.invalidate(c10["case_id"], cur1, now=1002)
    job1 = r1["job"]
    cur2 = case(case_id=c10["case_id"], raw_sha256="8" * 64)
    r2 = g10.invalidate(c10["case_id"], cur2, now=1003)
    T("F1 queued 期间连续变化 → 同一 job、change_set 合并",
      r2.get("job_created") is False and r2["job"]["job_id"] == job1["job_id"]
      and len(r2["job"]["change_set"]) >= 1, str(r2))
    g10.start_job(c10["case_id"], now=1004)
    cur3 = case(case_id=c10["case_id"], kb_snapshot={"version": "kb-3", "hash": "7" * 64})
    r3 = g10.invalidate(c10["case_id"], cur3, now=1005)
    T("F2 running 期间再变化 → successor（新 job），不动 running 快照",
      r3.get("job_created") is True and r3["job"]["state"] == "queued"
      and r3["job"]["job_id"] != job1["job_id"], str(r3))
    g10.complete_job(c10["case_id"], now=1006)
    st = g10.state(c10["case_id"])
    T("F3 running 完成但 successor 未完成 → 仍 invalidated",
      st["status"] == "invalidated", str(st))
    g10.start_job(c10["case_id"], now=1007)
    g10.complete_job(c10["case_id"], now=1008)
    st = g10.state(c10["case_id"])
    T("F4 全部重审完成 → 回 pending_release / 待放行",
      st["status"] == "pending_release" and st["release_status"] == "待放行", str(st))
    tk_new = token(s10, s, c10, nonce="re-sign")
    sig2 = g10.sign(c10, s, tk_new, "re-sign", reason="test", now=1009)
    old_sig_id = g10.signatures(c10["case_id"])[0]["signature_id"]
    T("F5 重审后可重新签发，新记录 derived_from 旧签名",
      len(g10.signatures(c10["case_id"])) == 2
      and sig2.get("derived_from") == old_sig_id, str(sig2.get("derived_from")))
    same1 = g10.invalidate(c10["case_id"], cur3, now=1010)
    same2 = g10.invalidate(c10["case_id"], cur3, now=1011)
    T("F6 同 change_set 重复投递 → 幂等（第二次不重复建 job）",
      same1.get("invalidated") is True and same2.get("invalidated") is False
      and same2.get("job_created") is False, str({ "first": same1, "second": same2 }))

    # ── G 机器不可写放行 ────────────────────────────────────────────
    g11, _, c11 = signed_case("g11")
    must_deny("G1 机器 patch 写 release_status → 拒",
              lambda: g11.apply_machine_patch(c11["case_id"], {"release_status": "已放行"}),
              MachineWriteDenied)
    g11.apply_machine_patch(c11["case_id"], {"note": "ok"})
    T("G2 非 release_status 的 patch 允许", g11.state(c11["case_id"])["case"].get("note") == "ok", "")

    # ── H 签名不可变 ────────────────────────────────────────────────
    sigs = gate.signatures("case-1")
    tampered = dict(sigs[0], reason="被改了")
    T("H1 旧签名被改 → validate 红", validate_signature(tampered) != [], "")
    tampered_media = dict(sigs[0], media_fingerprints_root_hash="0" * 64)
    T("H2 media root 被改 → 红", validate_signature(tampered_media) != [], "")
    T("H3 取出的签名是副本（改它不影响内部）",
      gate.signatures("case-1")[0]["reason"] == "人工复核通过", "")

    for f in fails:
        print("  ❌ " + f)
    verdict = "❌" if fails else "✅"
    print("\n%s verify_release_gate %d 项检查 · %d 项红" % (verdict, checks, len(fails)))
    shutil.rmtree(TMP, ignore_errors=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
