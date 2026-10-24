#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ADR-0016 T1：生产判定入口 RuleJudge + Orchestrator 自证。

主体：base/judge_entry.py、base/rule_judge.py、base/orchestrator.py、base/decision_table.py。
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from base import contract as C
    from base.judge_entry import judge_unit
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 judge_entry: %s" % exc)
    sys.exit(2)


def main():
    passed = failed = 0

    def report(ok, name, detail=""):
        nonlocal passed, failed
        ok = bool(ok)
        print(("PASS" if ok else "FAIL") + ": " + name +
              ((" " + detail) if detail else ""),
              file=sys.stdout if ok else sys.stderr)
        passed += int(ok)
        failed += int(not ok)

    unit = C.from_media(
        "image", b"image", "hospital grade breast pump",
        uri="inline:image", extractor="test",
        covers=["图内文字"], does_not_cover=["画面语义"])
    unit["parse_status"] = "ok"
    r1 = judge_unit(unit, clock=lambda: 1000)
    r2 = judge_unit(unit, clock=lambda: 1000)
    report(r1["steps"] == ["normalize", "judge", "dispose", "output", "evaluate"],
           "C0 五步固定顺序各一次", repr(r1["steps"]))
    report(r1["release_status"] == "待放行"
           and r1["ir"]["decision"]["release_status"] == "待放行",
           "C1 release_status 恒待放行")
    report([f["finding_id"] for f in r1["findings"]] ==
           [f["finding_id"] for f in r2["findings"]],
           "C2 同一 unit 的 finding_id 确定性")
    report(r1["ir"]["content_unit_ref"] == {
        "unit_id": unit["unit_id"], "kind": "image", "parse_status": "ok"},
        "C3 ReviewIR 指向 image/ok ContentUnit", repr(r1["ir"]["content_unit_ref"]))
    media_fp = r1["ir"].get("media_fingerprints") or {}
    report(all(media_fp.get(key) for key in (
        "frame_manifest_hash", "ocr_output_hash", "asr_output_hash",
        "model_config_hash")),
        "C3b 图片 ReviewIR 带四类独立媒体指纹", repr(media_fp))
    report(r1["ir"]["coverage"]["coverage_state"] == "partial"
           and r1["label"] != "PASS",
           "C4 图片画面语义未覆盖 → partial 永不 PASS")

    # R1 把唯一 RuleJudge 换成空命中：仍因图片 partial 落 REVIEW，不许 PASS。
    with mock.patch("base.rule_judge.RuleJudge.judge", return_value=[]):
        empty = judge_unit(unit, clock=lambda: 1000)
    report(empty["findings"] == [] and empty["label"] == "REVIEW"
           and empty["ir"]["coverage"]["coverage_state"] == "partial",
           "R1 RuleJudge 空命中 → REVIEW/partial，不许 PASS", repr(empty["label"]))

    failed_unit = C.from_media(
        "image", b"image", "", uri="inline:failed", extractor="test",
        covers=["失败观测"], does_not_cover=[])
    failed_unit.update({
        "parse_status": "failed", "failure_kind": "parse_error",
        "reason": "OCR parse_error",
    })
    calls = [0]

    def should_not_run(*_args, **_kwargs):
        calls[0] += 1
        raise AssertionError("failed unit 不应进入 RuleJudge")

    with mock.patch("base.rule_judge.RuleJudge.judge", side_effect=should_not_run):
        failed_result = judge_unit(failed_unit, clock=lambda: 1000)
    report(calls[0] == 0 and failed_result["label"] == "未审查"
           and failed_result["layer"] == "DP0"
           and failed_result["ir"]["content_unit_ref"]["failure_kind"] ==
           "parse_error",
           "C5 failed unit 不调 RuleJudge，落未审查/DP0")

    # ── C6–C9（T-316b）：report_snapshot 必须被透传出去 ──────────────
    #
    # 为什么这四条要住在本文件而不是 verify_report_store.py：
    # 缺口在 judge_entry 的**返回值**上（Orchestrator 产出、judge_entry 丢掉），
    # 而 ReportStore 一直是好的 —— 把它放进报告验证器，会让「谁丢了它」这件事
    # 查错方向。§2.4.7：判据要盖住事故发生的那一跳。
    snap = r1.get("report_snapshot")
    report(snap is not None,
           "C6 report_snapshot 被 judge_entry 透传（不是 None）",
           "keys=%r" % (sorted(r1),))
    report(isinstance(snap, dict) and snap.get("ir") == r1["ir"],
           "C7 snapshot.ir 与本次判定的 IR 是同一个（不是另一份）", "")
    # 渲染器要的六键；只断言「在不在」，不重抄渲染器的校验（两份必然漂移）
    need = {"ir", "failure_kind_counts", "unknown_bucket_counts",
            "evidence", "unassessed", "receipt"}
    report(isinstance(snap, dict) and need <= set(snap),
           "C8 snapshot 含渲染器要求的六键",
           "missing=%r" % (sorted(need - set(snap or {})),))
    # ★ 反向面：failed unit（未审查/DP0）也必须带 snapshot。
    #   这一条防的是「只在 OK 路径上透传」那种写法 —— 而 failed 报告同样要出。
    report(failed_result.get("report_snapshot") is not None,
           "C9 failed unit 也带 report_snapshot（未审查报告同样要能渲染）",
           "label=%r" % (failed_result.get("label"),))

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
