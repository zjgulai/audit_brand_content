#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_release_gate.py —— `base/release_gate.py` 的判据（T2-03 / RL-1…RL-15）

## 它验什么

  A **状态机**：pending_release → signed / rejected；signed → revoked；
    signed → invalidated →（重审完成后）pending_release；非法迁移必须拒。
  B **签发绑定全字段**：case_version / IR id+version / raw+text / rule+kb 快照
    （version+hash）/ used_authority_refs / conflict_table_version / 六类媒体指纹 +
    root hash / signature_version；缺一或签名被改 → 红。
  B8–B10（2026-10-23 变异复查 #126/#127 补）：签发绑定**逐字段与 case 对拍**
    （kb_snapshot 被绑成 rule_snapshot、keyframe 被绑成 frame 必红）；
    生产 SIGNATURE_FIELDS 与验收器**自己的**清单恒等（清单收窄必红 ——
    B1 用生产常量自证，清单收窄在 B1 不可见）；四类媒体指纹各一枚独立
    （两类同值 = 压成一枚，失效源不可定位，必红）。
  C **SoD**：提交人、最终复核人不可签；跨租户/品线/无 release.sign → 拒。
  D **step-up**：必须消费；重复使用、错误 action/nonce、过期 → 拒（接 auth_session）。
  E **失效五类**：content / rule_snapshot / kb_snapshot / used ref versions /
    conflict_table_version；**未使用的 ref 变化不触发**（SB-8）。
  F **重审 job**：invalidated 必须自动建 job；queued 合并 change_set（**两次变化
    都必须在 change_set 里**，丢一次即红 —— 2026-10-23 变异复查 #102 补）；
    running 时新建 successor；同 change_set 幂等；完成后回 pending_release。
  G **机器不可写放行**：任何 patch 带 release_status → 拒。
  H **签名不可变**：旧签名被改 → validate 红；重新签发 = 新记录 + derived_from。

## 退出码

  0 全过 · 1 有红 · 2 未测（导入失败之外的不可测条件）

## --controls（反向对照）

  好样本 → 0 · 坏样本 → 各自非零。反向对照清单：
    C-1 判定器对真签名必须闭嘴（反向：喂好样本不许红 —— 不许修成哑巴）
    C-2 B8 kb 绑定拍 case 必须拦「绑成 rule_snapshot」（坏样本：偏判后的签名）
    C-3 B8 绑定拍 case 必须拦「field 收窄」（坏样本：SIGNATURE_FIELDS 删 kb_snapshot_hash）
    C-4 B8 媒体指纹必须拦「压成一枚」（坏样本：keyframe == frame）
    C-5 F1a 合并必须拦「丢第一次变化」（坏样本：_merge 只留最后一次）
    C-6 B9 必须拦「验收器清单缩窄」（坏样本：本表清单删 ocr_output_hash）
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
        ReleaseGate, SIGNATURE_FIELDS, SIGNATURE_VERSION, SignatureError,
        StepUpError, SoDViolation, InvalidTransition, MachineWriteDenied,
        media_root, validate_signature)
except Exception as e:  # noqa: BLE001
    print("❌ 导入 base/release_gate.py / auth_session 失败：%s" % e)
    sys.exit(1)


# ── 验收器自己的清单（B9 反向对照的判据，不 import 生产的）──────────────
#   与 release_gate.SIGNATURE_FIELDS 的 27 个签发绑定字段恒等；生产侧收窄
#   （如 #126 删 kb_snapshot_hash、#127 删 ocr_output_hash）在 B9 必红。
#   ★ 这份清单自己被 --controls C-6 看着：它自己缩窄时 --controls 必须红。
EXPECTED_SIGNATURE_FIELDS = {
    "signature_id", "signature_version", "case_id", "case_version",
    "ir_id", "ir_version", "raw_sha256", "text_sha256",
    "rule_snapshot_version", "rule_snapshot_hash",
    "kb_snapshot_version", "kb_snapshot_hash",
    "used_authority_refs", "conflict_table_version",
    "frame_manifest_hash", "keyframe_set_hash", "ocr_output_hash",
    "asr_output_hash", "model_config_hash", "sampling_config_hash",
    "media_fingerprints_root_hash", "signer_id", "signed_at",
    "step_up_ref", "decision", "reason", "signature_hash",
}

# 签发绑定必须与 case 逐字段对拍的条目（B8）：签名字段 → case 字段 → label。
# kb 绑成 rule（#126 变异一）、keyframe 绑成 frame（#127 变异一）都在这里拦。
_BIND_TO_CASE = (
    ("case_version", "case_version"),
    ("ir_id", "ir_id"), ("ir_version", "ir_version"),
    ("raw_sha256", "raw_sha256"), ("text_sha256", "text_sha256"),
    ("rule_snapshot_version", ("rule_snapshot", "version")),
    ("rule_snapshot_hash", ("rule_snapshot", "hash")),
    ("kb_snapshot_version", ("kb_snapshot", "version")),
    ("kb_snapshot_hash", ("kb_snapshot", "hash")),
    ("conflict_table_version", "conflict_table_version"),
    ("frame_manifest_hash", "frame_manifest_hash"),
    ("keyframe_set_hash", "keyframe_set_hash"),
    ("ocr_output_hash", "ocr_output_hash"),
    ("asr_output_hash", "asr_output_hash"),
    ("model_config_hash", "model_config_hash"),
    ("sampling_config_hash", "sampling_config_hash"),
)


def _sig_binding_mismatch(sig, case):
    """B8 判定器：签名里的绑定值必须与 case 的原值逐字段相等。

    返回不相等的字段清单（空 = 通过）。独立于生产的 _binding()/SIGNATURE_FIELDS，
    只对拍值本身 —— 生产把 kb 绑成 rule、keyframe 绑成 frame 时，值不相等即红。
    """
    out = []
    for sig_field, case_field in _BIND_TO_CASE:
        if isinstance(case_field, tuple):
            snap = case.get(case_field[0])
            case_val = snap.get(case_field[1]) if isinstance(snap, dict) else None
        else:
            case_val = case.get(case_field)
        if sig.get(sig_field) != case_val:
            out.append("%s=%r != case.%s=%r" % (sig_field, sig.get(sig_field),
                                                case_field, case_val))
    case_refs = sorted("%s:%s" % (r.get("ref_id"), r.get("version"))
                       for r in (case.get("used_authority_refs") or []))
    sig_refs = sorted("%s:%s" % (r.get("ref_id"), r.get("version"))
                      for r in (sig.get("used_authority_refs") or []))
    if sig_refs != case_refs:
        out.append("used_authority_refs=%r != case=%r" % (sig_refs, case_refs))
    return out


# 四类逐项媒体指纹（TS-24）：各一枚独立指纹，不是一枚总指纹。
_FOUR_MEDIA = ("frame_manifest_hash", "keyframe_set_hash",
               "ocr_output_hash", "asr_output_hash")


def _collapsed_media(sig):
    """B10 判定器：四类指纹里出现「两类同值」= 压成一枚 → 失效源不可定位。

    返回同值对（空 = 通过）。把 keyframe_set_hash 绑成 frame_manifest_hash
    （#127 变异一）在这里红。
    """
    seen = {}
    for f in _FOUR_MEDIA:
        seen.setdefault(str(sig.get(f)), []).append(f)
    return [v for v in seen.values() if len(v) > 1]


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

    # ── A7 撤回权不随签发权自动获得（行 91）─────────────────────────
    #   ★ 夹具必须**分开能力**：`signer()` 默认同时给 release.sign + release.revoke，
    #     用它做撤回测试会把这个缺陷整个盖住（2026-10-23 审计指出）。
    def _signed_for(prefix, cid, sign_principal):
        g, ss = new_gate(prefix)
        cc = case(case_id=cid)
        g.sign(cc, sign_principal,
               token(ss, sign_principal, cc, nonce="s-" + cid),
               "s-" + cid, reason="test", now=1001)
        return g, ss, cc

    p_sign_only = signer("u3", capabilities=["release.sign"])
    g7, s7, c7 = _signed_for("a7", "case-7", p_sign_only)
    tk7 = token(s7, p_sign_only, c7, action="revoke", nonce="rv7")
    try:
        g7.revoke(c7, p_sign_only, tk7, "rv7", reason="x")
        T("A7a 只有签发权 → 撤回被拒", False, "未拒 —— 撤回权随签发权自动获得了")
    except SoDViolation:
        T("A7a 只有签发权 → 撤回被拒", True, "")

    # ★ A7b 随 T-315b / #123c 重排：撤回绑定**原签发人** —— 撤回权独立的
    #   反向对照改用「u4 是 case-8 的原签发人、且只有 release.revoke」，
    #   证明「撤回不随签发权自动获得」的同时不暗示「可撤别人的」。
    # ★ A7b 的可行形状：签发时必然持有 release.sign（否则签不了），
    #   「只有撤回权」只能出现在**签发之后能力被撤**（撤权）的场景 ——
    #   这正是 #123(a) 撤权后原签发人仍可撤回的判定。
    p_revoke_only = signer("u4", capabilities=["release.sign", "release.revoke"])
    g8, s8, c8 = _signed_for("a8", "case-8", p_revoke_only)
    p_after_revoke = signer("u4", capabilities=["release.revoke"])
    tk8 = token(s8, p_after_revoke, c8, action="revoke", nonce="rv8")
    try:
        g8.revoke(c8, p_after_revoke, tk8, "rv8", reason="内容修改", now=1002)
        T("A7b 只有撤回权的原签发人 → 撤回放行（反向对照：不是一律拒绝）",
          g8.state("case-8")["status"] == "revoked", str(g8.state("case-8")))
    except Exception as e:  # noqa: BLE001
        T("A7b 只有撤回权的原签发人 → 撤回放行（反向对照：不是一律拒绝）", False,
          "%s: %s" % (type(e).__name__, e))

    # A7d（T-315b / #123c）：持 release.revoke 但**不是**原签发人 → 拒。
    #   这条判定 2026-10-25 之前不存在（任何人可撤任何人的签发）。
    p_other_revoker = signer("u9", capabilities=["release.revoke"])
    g9d, s9d, c9d = _signed_for("a9d", "case-9d", p_sign_only)
    tk9d = token(s9d, p_other_revoker, c9d, action="revoke", nonce="rv9d")
    try:
        g9d.revoke(c9d, p_other_revoker, tk9d, "rv9d", reason="x")
        T("A7d 撤回绑定原签发人（#123c）→ 非原签发人被拒", False, "未拒")
    except SoDViolation:
        T("A7d 撤回绑定原签发人（#123c）→ 非原签发人被拒", True, "")

    p_none = signer("u5", capabilities=[])
    g9, s9, c9 = _signed_for("a9", "case-9", p_sign_only)
    tk9 = token(s9, p_none, c9, action="revoke", nonce="rv9")
    try:
        g9.revoke(c9, p_none, tk9, "rv9", reason="x")
        T("A7c 两个能力都无 → 撤回被拒", False, "未拒")
    except SoDViolation:
        T("A7c 两个能力都无 → 撤回被拒", True, "")

    # ── B 签发绑定全字段 ────────────────────────────────────────────
    T("B1 签名包含全部绑定字段", set(SIGNATURE_FIELDS) <= set(sig), str(sorted(set(SIGNATURE_FIELDS) - set(sig))))
    # B9（#126/#127 变异二补）：生产 SIGNATURE_FIELDS 与验收器**自己的**清单恒等。
    #   B1 用生产常量自证 —— 生产把字段删掉（kb_snapshot_hash / ocr_output_hash）
    #   B1 反而变绿；只有拿验收器自己的清单做下界才能看见收窄。
    T("B9 生产字段清单 ⊇ 验收器自己的清单（收窄必红）",
      EXPECTED_SIGNATURE_FIELDS <= set(SIGNATURE_FIELDS),
      "生产侧缺：" + str(sorted(EXPECTED_SIGNATURE_FIELDS - set(SIGNATURE_FIELDS))))
    T("B2 validate_signature 对真签名零错误", validate_signature(sig) == [], str(validate_signature(sig)))
    T("B2b 签名只存不可逆 step-up ref，不存 bearer token",
      sig["step_up_ref"].startswith("stepup:") and sig["step_up_ref"] != tk
      and tk not in json.dumps(sig, ensure_ascii=False), str(sig["step_up_ref"]))
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

    # ── B8/B10 逐字段对拍（#126/#127 变异一补）────────────────────────
    #   B3/B4 只验「改一个字段签名哈希不符」，从不与 **case 的原值**对拍：
    #   生产把 kb_snapshot 绑成 rule_snapshot（_binding:155 的 kv,kh 换成 rv,rh）、
    #   把 keyframe_set_hash 绑成 frame_manifest_hash 时，签名仍内部自洽、B1–B7 全绿。
    #   B8 对拍值本身，B10 拦「四类指纹压成一枚」。
    gB8, sessB8 = new_gate("b8")
    sigB8 = gB8.sign(case(case_id="case-b8"), s,
                     token(sessB8, s, case(case_id="case-b8"), nonce="b8"),
                     "b8", reason="test", now=1001)
    cB8 = case(case_id="case-b8")
    T("B8 签发绑定与 case 逐字段相等（kb 不得绑成 rule、keyframe 不得绑成 frame）",
      _sig_binding_mismatch(sigB8, cB8) == [],
      "; ".join(_sig_binding_mismatch(sigB8, cB8)))
    T("B10 四类媒体指纹各一枚独立（不得压成一枚总指纹）",
      _collapsed_media(sigB8) == [], str(_collapsed_media(sigB8)))
    T("B10b 四类指纹确实互不相同（fixture 自检，防同值 fixture 恒真）",
      len({cB8[f] for f in _FOUR_MEDIA}) == len(_FOUR_MEDIA), str(cB8))

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
    # ★ 两次变化走**不同字段**（raw / conflict_table）：change_set 按 field 归并，
    #   同字段连续变化按语义本就折叠成一条（只留最新值）；只有不同字段才谈得上
    #   「合并丢一条」—— 这也是 #102 那个变异（_merge 只留一次变化）可观察的前提。
    cur1 = case(case_id=c10["case_id"], raw_sha256="9" * 64)
    r1 = g10.invalidate(c10["case_id"], cur1, now=1002)
    job1 = r1["job"]
    cur2 = case(case_id=c10["case_id"], conflict_table_version="ct-2")
    r2 = g10.invalidate(c10["case_id"], cur2, now=1003)
    T("F1 queued 期间连续变化 → 同一 job、change_set 合并",
      r2.get("job_created") is False and r2["job"]["job_id"] == job1["job_id"]
      and len(r2["job"]["change_set"]) >= 1, str(r2))
    # F1a（#102 变异补）：RL-14「缺一条即红」—— 合并只留一次变化（无论留头还是
    #   留尾）时，F1 的 >=1 依旧全绿。合并后的 change_set 必须**两次变化都在**：
    #   第一次（raw 1→9…）与第二次（conflict ct-1→ct-2）各一条，缺一即红。
    cs = r2["job"]["change_set"]
    T("F1a 合并保留两次变化的完整内容（RL-14 缺一条即红）",
      any(x.get("field") == "raw_sha256" and x.get("new_version") == "9" * 64
          for x in cs)
      and any(x.get("field") == "conflict_table_version"
              and x.get("new_version") == "ct-2" for x in cs),
      "change_set=%s" % json.dumps(cs, ensure_ascii=False))
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


def _controlled(cid, sig, case_dict, mut):
    """--controls 共用判定器：B8/B9/B10 三个判定器 + F1a 的合并判据，
    喂一份样本返回红项清单（空 = 该组全过）。好样本必须全空（C-1），
    五类坏样本必须各自非空（C-2…C-6）。"""
    bad = []
    if _sig_binding_mismatch(sig, case_dict):
        bad.append(cid + "-B8")
    if not (EXPECTED_SIGNATURE_FIELDS <= set(mut["fields"])):
        bad.append(cid + "-B9")
    if _collapsed_media(sig):
        bad.append(cid + "-B10")
    return bad


def run_controls():
    """--controls：好样本必须闭嘴，五类坏样本必须各自红（§2.4.1：没红过的断言不算验证过它）。"""
    results = []

    def ok(name, cond, detail=""):
        results.append((name, bool(cond), detail))

    tmp = tempfile.mkdtemp(prefix="rg_ctl_")
    s = signer()
    # C-1 好样本：真实签发，判定器必须全空（不许把验证器修成哑巴）
    sessions = SessionStore(os.path.join(tmp, "ctl.db"))
    g = ReleaseGate(sessions=sessions)
    c_good = case(case_id="ctl-good")
    sig_good = g.sign(c_good, s, sessions.issue_step_up(
        s["id"], c_good["case_id"], "sign", "n1", now=1000),
        "n1", reason="test", now=1001)
    mut_good = {"fields": set(SIGNATURE_FIELDS)}
    bad = _controlled("good", sig_good, c_good, mut_good)
    ok("C-1 好样本 → 判定器全部闭嘴", bad == [], str(bad))

    # C-2 坏样本（#126 变异一）：kb_snapshot 被绑成 rule_snapshot
    sig_kb = dict(sig_good)
    sig_kb["kb_snapshot_version"] = sig_good["rule_snapshot_version"]
    sig_kb["kb_snapshot_hash"] = sig_good["rule_snapshot_hash"]
    bad = _controlled("c2", sig_kb, case(case_id="ctl-good"), mut_good)
    ok("C-2 kb 绑成 rule_snapshot → B8 红", "c2-B8" in bad, str(bad))

    # C-3 坏样本（#126 变异二）：SIGNATURE_FIELDS 删 kb_snapshot_hash
    mut_narrow = {"fields": set(SIGNATURE_FIELDS) - {"kb_snapshot_hash"}}
    bad = _controlled("c3", sig_good, case(case_id="ctl-good"), mut_narrow)
    ok("C-3 字段清单收窄（删 kb_snapshot_hash）→ B9 红", "c3-B9" in bad, str(bad))

    # C-4 坏样本（#127 变异一）：keyframe_set_hash 绑成 frame_manifest_hash（压成一枚）
    sig_col = dict(sig_good)
    sig_col["keyframe_set_hash"] = sig_good["frame_manifest_hash"]
    bad = _controlled("c4", sig_col, case(case_id="ctl-good"), mut_good)
    ok("C-4 keyframe 压成 frame 一枚 → B8+B10 红",
       "c4-B8" in bad and "c4-B10" in bad, str(bad))

    # C-5 坏样本（#102）：合并丢第一次变化 → F1a 判据红（两条异字段变化，留尾丢头）
    cs_full = [{"field": "raw_sha256", "new_version": "9" * 64},
               {"field": "conflict_table_version", "new_version": "ct-2"}]
    cs_dropped = cs_full[1:]           # _merge 只留最后一次的形状
    def _f1a(cs):
        return (any(x.get("field") == "raw_sha256"
                    and x.get("new_version") == "9" * 64 for x in cs)
                and any(x.get("field") == "conflict_table_version"
                        and x.get("new_version") == "ct-2" for x in cs))
    ok("C-5 完整合并 → F1a 闭嘴；丢第一次 → 红",
       _f1a(cs_full) and not _f1a(cs_dropped), str(cs_dropped))

    # C-6 反向对照（对着验收器自己的清单）：这份清单自己缩窄时 B9 必须红
    mut_self = {"fields": EXPECTED_SIGNATURE_FIELDS - {"ocr_output_hash"}}
    bad = _controlled("c6", sig_good, case(case_id="ctl-good"), mut_self)
    ok("C-6 验收器清单自己缩窄 → B9 红", "c6-B9" in bad, str(bad))

    passed = sum(1 for _, p, _ in results if p)
    for name, p, detail in results:
        print("  %s %s  %s" % ("✓" if p else "✗", name, detail))
    print("\n%s verify_release_gate --controls %d/%d" %
          ("✅" if passed == len(results) else "✗", passed, len(results)))
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(run_controls() if "--controls" in sys.argv[1:] else main())
