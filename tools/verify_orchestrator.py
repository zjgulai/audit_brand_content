#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_orchestrator.py — T1-15：五步串联 + ReviewIR 组装 + 回执

覆盖：
  C0  五步固定顺序 normalize→judge→dispose→output→evaluate，各恰好一次
  C1  部件可注入，且每个部件恰好调用一次（无轮次）
  C2  ReviewIR 必填字段 + decision/coverage/content_unit_ref
  C3  Receipt 17 字段；skipped=[]；steps 五条；disposition/video_sampling
  C4  parse_status=failed → judge 0 次、findings=[]、无 judge 标签、控制点未跑
  C5  回执记实际 control_points_version
  C6  高严重度命中也不提前停：五步全跑
  R1  调换两步顺序 → 红
  R2  判定被调用两次 → 红
  R3  跳步 → 红
  R4  receipt 缺字段 → 红
  R5  failed 却调用 judge → 红
  R6  skipped 缺失 → 红

退出码：0 全过 / 1 有红 / 2 未测（导入失败或验收器自身异常）。
"""

import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

try:
    from base import orchestrator as O
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 base.orchestrator: %s" % exc)
    sys.exit(2)


def unit(parse_status="ok", failure_kind=None):
    return {
        "unit_id": "cu-1",
        "contract_version": "content-unit-v1",
        "source": {"kind": "free_text"},
        "parse_status": parse_status,
        "failure_kind": failure_kind,
        "text": "一段正文",
        "textification": {"covers": ["正文"], "does_not_cover": []},
    }


def request(**over):
    r = {
        "unit": unit(),
        "control_points": ["H01", "H02"],
        "control_points_version": "cp-test-v9",
        "rule_snapshot": "rs-1",
        "kb_snapshot": "kb-1",
        "skill_id": "skill-1",
        "skill_version": "1.0",
        "skill_hash": "sh-1",
        "video_sampling": {"interval_ms": 500, "total_frames": 30},
        "report_url": "https://example.test/reports/ir-1.md",
    }
    r.update(over)
    return r


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

    ir_schema = json.loads(open(
        os.path.join(REPO_ROOT, "contracts", "review-ir-v1.schema.json"),
        encoding="utf-8").read())
    rc_schema = json.loads(open(
        os.path.join(REPO_ROOT, "contracts", "receipt-v1.schema.json"),
        encoding="utf-8").read())
    ir_required = set(ir_schema["required"])
    rc_required = set(rc_schema["required"])

    finding = {
        "finding_id": "f-1", "control_code": "H01", "status": "confirmed",
        "severity": "L5", "produced_by": "rule", "derived_from": None,
        "authority_state": "ok", "detected_by": "P0",
        "location": {"type": "image", "bbox": [0.1, 0.2, 0.4, 0.6]},
        "quote": "原文", "evidence_id": "E-1",
    }
    candidate = {
        "finding_id": "f-2", "control_code": "H02", "status": "candidate",
        "severity": "L3", "produced_by": "semantic", "derived_from": None,
        "authority_state": None, "detected_by": "P1",
    }
    coverage = {
        "coverage_state": "partial",
        "modalities_evaluated": ["free_text"],
        "rules_version": "rs-1",
        "control_points_applied": ["H01", "H02"],
        "not_evaluated_reason": [{"what": "视频音轨", "why": "no_capability"}],
    }
    decision = {
        "state": "BLOCK", "layer": "DP2", "release_status": "待放行",
        "obligations": ["partial_coverage"], "run_state": "OK",
    }
    disposition = {
        "state": "BLOCK", "layer": "DP2", "release_status": "待放行",
        "owner": "dp2", "due_at": "2026-10-22T00:00:00Z",
    }

    def build(counters, *, rule=None, sem=None, dec=None, unit_value=None):
        def comp(name, ret):
            def fn(ctx):
                counters[name] += 1
                return ret(ctx) if callable(ret) else ret
            return fn

        return O.Orchestrator(
            submission=comp("submission", lambda ctx: ctx["request"].get("unit")),
            normalizer=comp("normalizer", unit_value or unit()),
            rule_judge=comp("rule_judge", rule if rule is not None else [finding]),
            semantic_judge=comp("semantic_judge",
                                sem if sem is not None else {"status": "ok", "findings": [candidate]}),
            evidence=comp("evidence", lambda ctx: ctx["findings"]),
            coverage=comp("coverage", coverage),
            decision=comp("decision", dec if dec is not None else decision),
            disposition=comp("disposition", disposition),
            renderer=comp("renderer", {"rendered": True, "report_url": "r.md"}),
            store=comp("store", {"stored": True}),
            gateway=comp("gateway", {"sent": True}),
            evaluator=comp("evaluator", {"ok": True}),
        )

    from collections import Counter

    # C0/C1 五步顺序、各一次、每个部件一次
    counts = Counter()
    o = build(counts)
    r = o.run(request(unit=None))
    names = [s["name"] for s in r["receipt"]["steps"]]
    report(names == list(O.STEP_ORDER),
           "C0 五步固定顺序且各一次", repr(names))
    report(len(r["receipt"]["steps"]) == 5,
           "C0 步骤数恰好 5", repr(len(r["receipt"]["steps"])))
    report(all(c == 1 for c in counts.values()) and counts["rule_judge"] == 1
           and counts["semantic_judge"] == 1,
           "C1 每个注入部件恰好一次", repr(dict(counts)))
    report(r["run_state"] == "OK", "C0 run_state=OK", repr(r.get("run_state")))
    report(r["external_label"] == "BLOCK",
           "C0 正常路径 external_label=decision.state", repr(r.get("external_label")))

    # C2 ReviewIR
    ir = r["ir"]
    report(ir_required <= set(ir), "C2 ReviewIR 必填字段齐全",
           repr(sorted(ir_required - set(ir))))
    report(ir["content_unit_ref"]["unit_id"] == "cu-1"
           and ir["decision"]["state"] == "BLOCK"
           and ir["decision"]["release_status"] == "待放行"
           and ir["coverage"]["coverage_state"] == "partial",
           "C2 ReviewIR decision/coverage/content_unit_ref", repr(ir))
    report(ir["receipt_ref"] == r["receipt"]["receipt_id"],
           "C2 ReviewIR.receipt_ref == receipt_id", "")

    # C3 Receipt
    rc = r["receipt"]
    report(rc_required <= set(rc), "C3 Receipt 17 字段齐全",
           repr(sorted(rc_required - set(rc))))
    report(rc.get("skipped") == [], "C3/R6 skipped=[] 且不省略", repr(rc.get("skipped")))
    report(len(rc["steps"]) == 5
           and all({"name", "input_summary", "output_summary", "duration_ms"} <= set(s)
                   for s in rc["steps"]),
           "C3 steps 五条且字段齐全", repr(rc["steps"]))
    report(rc["obligations"] == ["partial_coverage"],
           "C3 回执带 obligations", repr(rc["obligations"]))
    report(rc["control_points_ran"] == ["H01", "H02"],
           "C3 回执带 control_points_ran", repr(rc["control_points_ran"]))
    report(rc["disposition"]["state"] == "BLOCK"
           and rc["disposition"]["release_status"] == "待放行",
           "C3 回执带 disposition", repr(rc["disposition"]))
    report(rc["video_sampling"] == {"interval_ms": 500, "total_frames": 30},
           "C3 回执带 video_sampling", repr(rc["video_sampling"]))
    report(rc["invariant_violation"] is None,
           "C3 invariant_violation=null（无违约）", repr(rc["invariant_violation"]))

    # C4 failed：judge 0 次、无 findings、无 judge 标签、控制点未跑
    c4 = Counter()

    def boom(_ctx):
        c4["judge"] += 1
        raise AssertionError("judge 不得被调用")

    failed_dec = {"state": "未审查", "layer": "DP0", "release_status": "待放行",
                  "obligations": [], "run_state": "OK"}
    o4 = build(c4, rule=boom, sem=boom, dec=failed_dec, unit_value=unit("failed", "parse_error"))
    r4 = o4.run(request(unit=None))
    report(c4["rule_judge"] == 0 and c4["semantic_judge"] == 0
           and r4["judge_invoked"] is False,
           "R5/C4 failed → judge 0 次", repr(dict(c4)))
    report(r4["findings"] == [], "C4 failed → findings=[]", repr(r4["findings"]))
    report(r4["external_label"] is None, "C4 failed → 不产 judge 标签",
           repr(r4.get("external_label")))
    report(r4["receipt"]["control_points_ran"] == [],
           "C4 failed → control_points_ran=[]",
           repr(r4["receipt"]["control_points_ran"]))
    report(r4["ir"]["decision"]["state"] == "未审查"
           and r4["ir"]["decision"]["layer"] == "DP0",
           "C4 failed → 结论落未审查/DP0", repr(r4["ir"]["decision"]))
    report(r4["receipt"]["disposition"]["state"] == "未审查"
           and r4["receipt"]["disposition"]["layer"] == "DP0",
           "C4 failed → 回执 disposition 也落未审查/DP0",
           repr(r4["receipt"]["disposition"]))
    report(r4["receipt"].get("skipped") == [],
           "C4 failed 也 skipped=[]", repr(r4["receipt"].get("skipped")))

    # C5 回执记实际 control_points_version
    report(r["receipt"]["control_points_version"] == "cp-test-v9"
           and r["ir"]["control_points_version"] == "cp-test-v9",
           "C5 回执/IR 记实际 control_points_version",
           repr((r["receipt"]["control_points_version"], r["ir"]["control_points_version"])))

    # C6 高严重度也不提前停
    c6 = Counter()
    r6 = build(c6).run(request(unit=None))
    report([s["name"] for s in r6["receipt"]["steps"]] == list(O.STEP_ORDER)
           and c6["evaluator"] == 1 and c6["renderer"] == 1,
           "C6 L5 命中也不提前停：output/evaluate 全部跑",
           repr(dict(c6)))

    # C7 默认部件（已交付模块）也能串联，不依赖注入
    r7 = O.Orchestrator().run(request())
    report(r7["run_state"] == "OK"
           and r7["steps"] == list(O.STEP_ORDER)
           and r7["receipt"].get("skipped") == [],
           "C7 默认部件串联成功（normalizer/coverage/decision/disposition）",
           json.dumps({"run_state": r7["run_state"], "steps": r7["steps"],
                       "state": r7["ir"]["decision"]["state"]}, ensure_ascii=False))

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
        import traceback
        tb = traceback.extract_tb(exc.__traceback__)
        if tb and os.path.basename(tb[-1].filename) == "orchestrator.py":
            print("FAIL: orchestrator 抛异常: %s: %s"
                  % (type(exc).__name__, exc), file=sys.stderr)
            sys.exit(1)
        print("UNTESTED: 验收器自身异常: %s" % exc)
        sys.exit(2)
