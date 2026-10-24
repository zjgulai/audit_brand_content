#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-310b 签发进权威的自证：reducer 三命令 + 真权威跨重启 + 投影可重建。

主体：base/review_reducer.py（RELEASE_COMMANDS / _release）、
base/release_binding.py（binding_from_state）、base/release_gate.py（validate_signature）、
base/business_event_store.py、base/projection_store.py。

设计纪律：案件到「已结案」走**真实生产链**（真 judge + 真 KB 的 prepare →
ingest → claim → submit_review），不手搓 state —— 签发绑定的就是这份 state。
签名由验证器按 service 层将要用的方式构造（binding + gate 字段集），
篡改样本各自必红。
"""
from __future__ import annotations

import copy
import hashlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from base.release_binding import binding_from_state
    from base.release_gate import (SIGNATURE_VERSION, _binding,
                                   signature_hash, validate_signature)
    from base.review_reducer import (RELEASE_COMMANDS, initial_state,
                                     reduce_command)
    from base.reviews_ledger import LedgerConflict, LedgerValidation
    from base.submission_service import SubmissionIngestor
    from base.business_event_store import BusinessEventStore, WriterLease
    from base.projector import Projector
    from base.projection_store import ProjectionStore
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入被测模块: %s" % exc)
    sys.exit(2)


def _closed_state(case_id):
    """真实生产链：prepare → ingest → claim → submit_review（结案）。"""
    ingestor = SubmissionIngestor()
    prepared = ingestor.prepare(
        {"submission_id": "sub-rel-" + case_id[-4:], "product_line": "home",
         "content_type": "文本", "content_stage": "final_content",
         "entry_channel": "群消息", "source": {"kind": "free_text"},
         "text": "限时特价，只要 9 元，立即点击购买"},
        principal={"tenant": "t-rel", "id": "u_sub"})
    payload = dict(prepared["payload"], case_id=case_id)
    state = initial_state(case_id)
    state, _, _ = reduce_command(state, "ingest_submission", "u_sub", 0,
                                 payload, now=5000)
    state, _, _ = reduce_command(state, "claim", "alice", state["version"],
                                 {}, now=5001)
    state, _, _ = reduce_command(
        state, "submit_review", "alice", state["version"],
        {"conclusion": {"review_notes": "逐条看过后结案"}}, now=5002)
    return state


def _make_sig(state, *, decision="signed", signer="u_signer", now=6000,
              tweak=None, retaint_hash=False):
    """按 service 层将要用的方式构造签名；tweak 用于篡改样本。"""
    # binding_from_state 的输出是 _binding() 的**输入**（case 形状）；
    # 签名体 = _binding() 的**输出**（扁平 27 字段）—— gate.sign 内部正是
    # sig = dict(_binding(case))。两层不要混。
    sig = _binding(binding_from_state(state))
    sig.update({
        "signature_id": "sig-" + hashlib.sha256(
            ("sig|%s|%s|%s" % (state["case_id"], decision, now))
            .encode("utf-8")).hexdigest()[:16],
        "signature_version": SIGNATURE_VERSION,
        "signer_id": signer,
        "signed_at": str(now),
        "step_up_ref": "stepup:test-ref",
        "decision": decision,
        "reason": "复核通过",
        "derived_from": None,
    })
    sig["signature_hash"] = signature_hash(sig)
    if tweak is not None:
        tweak(sig)
        if retaint_hash:
            # 模拟「改字段还重算哈希」的攻击者：结构与哈希自洽，但值是错的。
            # ★ 不 retaint 时**不重算**——重算会把篡改本身抹掉（R3d 第一版
            #   就这样把「哈希篡改必拒」测成了假红）。
            sig["signature_hash"] = signature_hash(sig)
    return sig


def _sign(state, sig, actor="u_signer", command="release_sign"):
    return reduce_command(state, command, actor, state["version"],
                          {"signature": sig}, now=6000)


def main():
    passed = failed = 0
    tmp_roots = []

    def report(ok, name, detail=""):
        nonlocal passed, failed
        ok = bool(ok)
        print(("PASS" if ok else "FAIL") + ": " + name +
              ((" " + detail) if detail else ""),
              file=sys.stdout if ok else sys.stderr)
        passed += int(ok)
        failed += int(not ok)

    def expect(kind, fn, code, name):
        try:
            fn()
            report(False, name, "（未拒绝）")
        except kind as exc:
            report(getattr(exc, "code", "") == code,
                   name, "（%s）" % getattr(exc, "code", ""))

    try:
        report(RELEASE_COMMANDS == frozenset(
            {"release_sign", "release_reject", "release_revoke"}),
            "R0 三条命令在册")

        state = _closed_state("case-rel-1")
        report(state["status"] == "closed" and state.get("release") is None,
               "R1 真实链到已结案、release 容器待首签")

        # ---- R2 快乐路径：sign → signed/已放行 ----
        sig = _make_sig(state)
        report(validate_signature(sig) == [],
               "R2a 验证器构造的签名过 validate_signature（结构自洽）")
        st2, _, res = _sign(state, sig)
        rel = st2["release"]
        report(rel["status"] == "signed" and rel["release_status"] == "已放行"
               and len(rel["signatures"]) == 1,
               "R2b release_sign 落容器：signed/已放行/一条签名")
        report(rel["events"][0]["kind"] == "release_signed"
               and rel["events"][0]["actor"] == "u_signer"
               and rel["events"][0]["step_up_ref"] == "stepup:test-ref",
               "R2c 事件带 kind/actor/step_up_ref")
        report(res["signature"]["signature_id"] == sig["signature_id"],
               "R2d 结果带出本次签名")
        report(st2["status"] == "closed",
               "R2e 签发不改变案件结案状态")

        # ---- R3 状态机与结构守卫（每条变异各自必红）----
        expect(LedgerConflict,
               lambda: _sign(st2, _make_sig(st2)),
               "invalid_transition", "R3a 已 signed 再签 → invalid_transition")

        def _sign_before_close():
            # 真实链到「已领案未结案」，签发必须被红线 R2 拦下。
            ingestor = SubmissionIngestor()
            prepared = ingestor.prepare(
                {"submission_id": "sub-rel-early", "product_line": "home",
                 "content_type": "文本", "content_stage": "final_content",
                 "entry_channel": "群消息", "source": {"kind": "free_text"},
                 "text": "限时特价，只要 9 元，立即点击购买"},
                principal={"tenant": "t-rel", "id": "u_sub"})
            s = initial_state("case-rel-early")
            s, _, _ = reduce_command(s, "ingest_submission", "u_sub", 0,
                                     dict(prepared["payload"],
                                          case_id="case-rel-early"), now=5000)
            s, _, _ = reduce_command(s, "claim", "alice", s["version"], {},
                                     now=5001)
            return _sign(s, _make_sig(s))
        expect(LedgerConflict, _sign_before_close,
               "invalid_transition", "R3b 未结案不许签发（红线 R2）")
        expect(LedgerValidation,
               lambda: _sign(state, _make_sig(state, decision="rejected",
                                              tweak=lambda s: None,
                                              retaint_hash=True),
                             command="release_sign"),
               "bad_signature", "R3c 命令与签名 decision 不一致 → 拒")
        expect(LedgerValidation,
               lambda: _sign(state, _make_sig(
                   state, tweak=lambda s: s.update({"signature_hash": "0" * 64})),
                   ),
               "bad_signature", "R3d 签名哈希篡改 → 拒")
        expect(LedgerValidation,
               lambda: _sign(state, _make_sig(
                   state,
                   tweak=lambda s: s.update({"case_version": state["version"] - 1}),
                   retaint_hash=True)),
               "bad_signature", "R3e 绑定旧版本（哈希自洽）→ 拒")
        expect(LedgerValidation,
               lambda: _sign(state, _make_sig(
                   state, tweak=lambda s: s.update({"case_id": "case-other"}),
                   retaint_hash=True)),
               "bad_signature", "R3f 绑定别的案件 → 拒")
        expect(LedgerValidation,
               lambda: _sign(state, _make_sig(
                   state, tweak=lambda s: s.pop("derived_from"))),
               "bad_signature", "R3g 缺 derived_from → 拒")

        # ---- R4 派生链：种子容器后，derived_from 必须等于上一条 ----
        seeded = copy.deepcopy(st2)
        seeded["release"]["status"] = "pending_release"
        seeded["release"]["release_status"] = "待放行"
        sig2_bad = _make_sig(seeded, now=7000)
        sig2_bad["derived_from"] = None
        sig2_bad["signature_hash"] = signature_hash(sig2_bad)
        expect(LedgerValidation, lambda: _sign(seeded, sig2_bad),
               "bad_signature", "R4a derived_from 不接上一条 → 拒")
        sig2_ok = _make_sig(seeded, now=7000)
        sig2_ok["derived_from"] = sig["signature_id"]
        sig2_ok["signature_hash"] = signature_hash(sig2_ok)
        st4, _, res4 = _sign(seeded, sig2_ok)
        report([s["signature_id"] for s in st4["release"]["signatures"]]
               == [sig["signature_id"], sig2_ok["signature_id"]]
               and st4["release"]["signatures"][1]["derived_from"]
               == sig["signature_id"],
               "R4b 链上第二条签名接 derived_from")
        # ---- R5 reject 路径 ----
        st5, _, res5 = _sign(_closed_state("case-rel-3"),
                             _make_sig(_closed_state("case-rel-3"),
                                       decision="rejected"),
                             command="release_reject")
        report(st5["release"]["status"] == "rejected"
               and st5["release"]["release_status"] == "已拒绝"
               and st5["release"]["events"][0]["kind"] == "release_rejected",
               "R5 release_reject → rejected/已拒绝")

        # ---- R6 revoke：只改状态 + 事件，不追加签名 ----
        st6, _, res6 = reduce_command(st2, "release_revoke", "u_revoker",
                                      st2["version"],
                                      {"reason": "发现新证据",
                                       "step_up_ref": "stepup:revoke-1"},
                                      now=8000)
        rel6 = st6["release"]
        report(rel6["status"] == "revoked" and rel6["release_status"] == "已撤回"
               and len(rel6["signatures"]) == 1
               and rel6["events"][-1]["kind"] == "release_revoked",
               "R6a revoke 置 revoked/已撤回、不追加签名")
        report(rel6["events"][-1]["reason"] == "发现新证据"
               and rel6["events"][-1]["step_up_ref"] == "stepup:revoke-1",
               "R6b 撤回事件带 reason 与 step_up_ref")
        st_rc = _closed_state("case-rel-4")
        expect(LedgerConflict,
               lambda: reduce_command(st_rc, "release_revoke", "u_r",
                                      st_rc["version"],
                                      {"reason": "x", "step_up_ref": "s"},
                                      now=8000),
               "invalid_transition", "R6c 未 signed 不可撤 → invalid_transition")
        expect(LedgerValidation,
               lambda: reduce_command(st2, "release_revoke", "u_r",
                                      st2["version"],
                                      {"reason": "  ", "step_up_ref": "s"},
                                      now=8000),
               "bad_revoke_reason", "R6d 撤回缺 reason → 拒")
        expect(LedgerValidation,
               lambda: reduce_command(st2, "release_revoke", "u_r",
                                      st2["version"],
                                      {"reason": "x", "step_up_ref": ""},
                                      now=8000),
               "bad_revoke_step_up_ref", "R6e 撤回缺 step_up_ref → 拒")

        # ---- P 段：真权威跨重启 + 投影可重建 ----
        root = tempfile.mkdtemp(prefix="release-persist-")
        tmp_roots.append(root)
        lease = WriterLease(os.path.join(root, "a", "lock")).acquire()
        auth = BusinessEventStore(os.path.join(root, "a"), lease=lease)
        cid = "case-rel-auth"
        ingestor = SubmissionIngestor()
        prepared = ingestor.prepare(
            {"submission_id": "sub-rel-auth", "product_line": "home",
             "content_type": "文本", "content_stage": "final_content",
             "entry_channel": "群消息", "source": {"kind": "free_text"},
             "text": "限时特价，只要 9 元，立即点击购买"},
            principal={"tenant": "t-rel", "id": "u_sub"})
        auth.execute(aggregate_id=cid, command="ingest_submission",
                     actor={"principal_id": "u_sub", "tenant_id": "t-rel"},
                     expected_version=0,
                     payload=dict(prepared["payload"], case_id=cid),
                     idempotency_key="ing", now=5000)
        auth.execute(aggregate_id=cid, command="claim",
                     actor={"principal_id": "alice", "tenant_id": "t-rel"},
                     expected_version=1, payload={}, idempotency_key="claim",
                     now=5001)
        auth.execute(aggregate_id=cid, command="submit_review",
                     actor={"principal_id": "alice", "tenant_id": "t-rel"},
                     expected_version=2,
                     payload={"conclusion": {"review_notes": "逐条看过后结案"}},
                     idempotency_key="close", now=5002)
        sig_auth = _make_sig(auth.state(cid))
        auth.execute(aggregate_id=cid, command="release_sign",
                     actor={"principal_id": "u_signer", "tenant_id": "t-rel"},
                     expected_version=3, payload={"signature": sig_auth},
                     idempotency_key="sign", now=6000)
        report(auth.state(cid)["release"]["status"] == "signed",
               "P1 签发经真权威落 state")

        auth2 = BusinessEventStore(os.path.join(root, "a"), lease=lease)
        rel_after = auth2.state(cid)["release"]
        report(rel_after["status"] == "signed"
               and rel_after["signatures"][0]["signature_hash"]
               == sig_auth["signature_hash"],
               "P2 重启恒等：签名与状态原样读回")

        proj = ProjectionStore(os.path.join(root, "p.db"))
        Projector(auth2, proj).catch_up()
        cased = proj.get_case(cid)
        report(cased is not None and (cased.get("release") or {}).get("status") == "signed"
               and cased["release"]["signatures"] == rel_after["signatures"],
               "P3 投影含 release 且与权威恒等")
        proj.reset()
        Projector(auth2, proj).catch_up()
        report(proj.get_case(cid)["release"] == rel_after,
               "P4 删投影重建后 release 恒等")
        proj.close()
    except AssertionError as exc:
        print("UNTESTED: 验收器内部断言失败: %s" % exc, file=sys.stderr)
        return 2
    finally:
        for r in tmp_roots:
            shutil.rmtree(r, ignore_errors=True)

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
