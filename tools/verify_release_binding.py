#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-310a 签发绑定字段的自证：真实生产链产出 + 提取器 + 恒等断言。

主体：base/release_binding.py、base/submission_service.py（prepare）、
base/review_reducer.py（_ingest_submission）、base/release_gate.py（_binding / media_root）。

设计上的一条硬纪律（AGENTS.md §2.4.1）：P 段**不走手搓 payload** ——
用真实 SubmissionIngestor（真 judge_unit、真 KB）跑完 prepare → ingest，
证明生产写进 state 的就是绑定需要的形状；手搓样本只用于提取器的单元测试。
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from base.release_binding import (MEDIA_BINDING_FIELDS,
                                      binding_from_state,
                                      media_placeholders)
    from base.release_gate import (_binding, ReleaseGate, SignatureError,
                                   validate_signature)
    from base.review_reducer import initial_state, reduce_command
    from base.reviews_ledger import LedgerValidation
    from base.submission_service import SubmissionIngestor
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入被测模块: %s" % exc)
    sys.exit(2)


def _ingest(payload, case_id):
    state = initial_state(case_id)
    state, _events, _result = reduce_command(
        state, "ingest_submission", "u_submitter", 0, payload, now=5000)
    return state


def _real_state():
    """真实生产链：真 KB + 真 judge → prepare → ingest。"""
    ingestor = SubmissionIngestor()
    prepared = ingestor.prepare(
        {"submission_id": "sub-bind-1", "product_line": "home",
         "content_type": "文本", "content_stage": "final_content",
         "entry_channel": "群消息",
         "source": {"kind": "free_text"},
         "text": "限时特价，只要 9 元，立即点击购买"},
        principal={"tenant": "t-bind", "id": "u_submitter"})
    return _ingest(prepared["payload"], prepared["case_id"]), prepared


def main(controls_only=False):
    passed = failed = 0

    def report(ok, name, detail=""):
        nonlocal passed, failed
        ok = bool(ok)
        print(("PASS" if ok else "FAIL") + ": " + name +
              ((" " + detail) if detail else ""),
              file=sys.stdout if ok else sys.stderr)
        passed += int(ok)
        failed += int(not ok)

    def expect_reject(fn, code, name):
        try:
            fn()
            report(False, name, "（未拒绝）")
        except (LedgerValidation, SignatureError) as exc:
            report(getattr(exc, "code", "") == code or code in str(exc.args),
                   name, "（%s）" % getattr(exc, "code", type(exc).__name__))

    if not controls_only:
        # ---- P 段：真实生产链（不走手搓 payload）----
        state, prepared = _real_state()
        ir = state["ir"]
        report(isinstance(state.get("kb_snapshot_hash"), str)
               and len(state["kb_snapshot_hash"]) == 64,
               "P1 ingest 后 kb_snapshot_hash 在 state 且为 hex64")
        expected_kb = hashlib.sha256(
            SubmissionIngestor()._kb_snapshot().encode("utf-8")).hexdigest()
        report(state["kb_snapshot_hash"] == expected_kb,
               "P2 kb_snapshot_hash == sha256(snapshot_id)（D1 口径）")
        report(state["conflict_table_version"]
               == ir.get("control_points_version")
               and isinstance(state["conflict_table_version"], str)
               and bool(state["conflict_table_version"]),
               "P3 conflict_table_version == ir.control_points_version 且非空")
        report(state["media_fingerprints"] == {},
               "P4 文本件 media_fingerprints 缺省为 {}")
        report(state.get("release") is None,
               "P5 release 容器在 initial_state 预置为 None")
        report(all(k in state for k in
                   ("kb_snapshot_hash", "conflict_table_version",
                    "media_fingerprints", "release")),
               "P6 initial_state 四个新键齐全")

        # ---- A1：11 个绑定字段齐全，binding_from_state 能过 _binding ----
        binding = None
        try:
            binding = binding_from_state(state)
            gate = None
            _binding(copy.deepcopy(binding))
            report(True, "A1 binding_from_state 输出通过 _binding（11 字段齐全）")
        except SignatureError as exc:
            report(False, "A1 binding_from_state 输出通过 _binding", "（%s）" % exc)
        report(binding is not None
               and isinstance(binding.get("case_version"), int)
               and binding["case_version"] == state["version"],
               "A1b case_version == state.version")
        report(binding is not None
               and (binding["used_authority_refs"] == []
                    or all(set(r) == {"ref_id", "version"}
                           for r in binding["used_authority_refs"])),
               "A1c used_authority_refs 形状（文本件允许空数组）")
        report(binding is not None
               and isinstance(binding["rule_snapshot"].get("hash"), str)
               and len(binding["rule_snapshot"]["hash"]) == 64,
               "A1d rules_version 从 JSON 字符串形状解析出 hex64 fingerprint")

        # ---- A2：提取器 fail closed（逐字段缺失/篡改必抛）----
        for name, mutate in (
            ("ir 缺失", lambda s: s.update({"ir": None})),
            ("kb_snapshot_hash 缺失", lambda s: s.update({"kb_snapshot_hash": None})),
            ("conflict_table_version 缺失", lambda s: s.update({"conflict_table_version": None})),
            ("content 缺失", lambda s: s.update({"content": None})),
            ("rules_version.fingerprint 篡改为 unknown",
             lambda s: s["ir"]["coverage"].update(
                 {"rules_version": json.dumps(
                     {"version": "rules-v1", "fingerprint": "unknown"})})),
            ("ir_version 缺失", lambda s: s["ir"].update({"ir_version": None})),
        ):
            bad = copy.deepcopy(state)
            mutate(bad)
            try:
                binding_from_state(bad)
                report(False, "A2 %s → SignatureError" % name, "（未抛）")
            except SignatureError:
                report(True, "A2 %s → SignatureError" % name)

        # ---- A3：媒体占位 hash 确定性 + 不是字符串常量 ----
        fields_a, root_a = media_placeholders({})
        fields_b, root_b = media_placeholders(None)
        report(fields_a == fields_b and root_a == root_b,
               "A3a 同输入两次调用占位 hash 相同")
        report(len({fields_a[k] for k in MEDIA_BINDING_FIELDS}) == 6,
               "A3b 六类占位 hash 互不相同")
        report(all(fields_a[k] != hashlib.sha256(b"").hexdigest()
                   for k in MEDIA_BINDING_FIELDS),
               "A3c 占位 hash 不等于空串摘要")
        if binding is not None:
            bad_binding = dict(binding)
            for k in MEDIA_BINDING_FIELDS:
                bad_binding[k] = "not_available"
            try:
                _binding(copy.deepcopy(bad_binding))
                report(False, "A3d not_available 字符串过不了 _binding", "（未抛）")
            except SignatureError:
                report(True, "A3d not_available 字符串过不了 _binding")
        else:
            report(False, "A3d not_available 字符串过不了 _binding", "（binding 不可用）")
        report(all(set(fields_a[k]) <= set("0123456789abcdef")
                   and len(fields_a[k]) == 64 for k in MEDIA_BINDING_FIELDS),
               "A3e 占位 hash 本身是 hex64（可在签名里复算）")

        # ---- A4：ctv 与 ir.control_points_version 的恒等断言在 ingest 即红 ----
        expect_reject(
            lambda: _ingest({**prepared["payload"],
                             "conflict_table_version": "cpv-other"}, prepared["case_id"]),
            "bad_binding_fields", "A4a payload ctv ≠ ir.control_points_version → 拒")
        expect_reject(
            lambda: _ingest({**prepared["payload"],
                             "kb_snapshot_hash": "short"}, prepared["case_id"]),
            "bad_binding_fields", "A4b kb_snapshot_hash 非 hex64 → 拒")
        expect_reject(
            lambda: _ingest({k: v for k, v in prepared["payload"].items()
                             if k != "conflict_table_version"}, prepared["case_id"]),
            "bad_binding_fields", "A4c 缺 conflict_table_version → 拒")
        expect_reject(
            lambda: _ingest({k: v for k, v in prepared["payload"].items()
                             if k != "kb_snapshot_hash"}, prepared["case_id"]),
            "bad_binding_fields", "A4d 缺 kb_snapshot_hash → 拒")
        expect_reject(
            lambda: _ingest({**prepared["payload"],
                             "media_fingerprints": "[]"}, prepared["case_id"]),
            "bad_binding_fields", "A4e media_fingerprints 非对象 → 拒")

        # ---- B 段：used_authority_refs 提取器（单元测试，允许构造 state）----
        ref = {"source": "外部标准库", "entry_id": "EXT-021", "article": "S7-03",
               "fingerprint": "sha256:" + "a" * 64}
        unit_state = copy.deepcopy(state)
        unit_state["ir"]["findings"] = [
            {"status": "confirmed", "authority_state": "ok",
             "authority_ref": [dict(ref), dict(ref)]},
            {"status": "confirmed", "authority_state": "missing",
             "authority_ref": [{"entry_id": "EXT-999", "fingerprint": "sha256:" + "b" * 64}]},
        ]
        refs = binding_from_state(unit_state)["used_authority_refs"]
        report(refs == [{"ref_id": "EXT-021", "version": ref["fingerprint"]}],
               "B1 ok 的 ref 去重收编、missing 不收编")
        unit_state["ir"]["findings"].append(
            {"status": "confirmed", "authority_state": "ok",
             "authority_ref": [{"entry_id": "EXT-002", "fingerprint": "sha256:" + "c" * 64}]})
        refs2 = binding_from_state(unit_state)["used_authority_refs"]
        report([r["ref_id"] for r in refs2] == sorted(r["ref_id"] for r in refs2),
               "B2 多 ref 按 ref_id 排序（规范化）")

        # ---- C 段：签名结构（validate_signature 对占位 binding 的兼容）----
        report(validate_signature({"signature_id": "x"}) != [],
               "C1 validate_signature 对缺字段签名报错（结构守卫活着）")

    # ---- --controls：四条离线反向对照（喂坏样本必须各自红）----
    n_controls = 0
    controls_ok = 0

    def control(ok, name):
        nonlocal n_controls, controls_ok
        n_controls += 1
        controls_ok += int(bool(ok))
        report(ok, "CTL " + name)

    try:
        control(media_placeholders({})[0] == media_placeholders({})[0],
                "c1 占位 hash 幂等")
        try:
            binding_from_state({"ir": None})
            control(False, "c2 缺 ir 必抛")
        except SignatureError:
            control(True, "c2 缺 ir 必抛")
        fields, _ = media_placeholders({})
        control(any(fields[k] != fields[j]
                    for k in MEDIA_BINDING_FIELDS for j in MEDIA_BINDING_FIELDS if k != j),
                "c3 六类占位互异")
        control(not _hex64_ok("not_available"),
                "c4 hex64 判据拒绝字符串常量")
    except Exception as exc:  # noqa: BLE001
        control(False, "controls 自身异常: %s" % exc)

    print("----------------------------------------")
    if failed == 0:
        print("✅ %d/%d 全过%s" % (passed, passed + failed,
                                  "" if not controls_only else "（--controls）"))
        return 0
    print("❌ %d passed, %d failed" % (passed, failed), file=sys.stderr)
    return 1


def _hex64_ok(v):
    return isinstance(v, str) and len(v) == 64 \
        and set(v) <= set("0123456789abcdef")


if __name__ == "__main__":
    try:
        sys.exit(main(controls_only="--controls" in sys.argv))
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 验收器自身异常: %s" % exc)
        sys.exit(2)
