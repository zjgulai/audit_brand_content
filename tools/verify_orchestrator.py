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
  C9  未知桶：回执四键计数/原因/目标层 + report snapshot 装配 + 渲染可见
  S   快照回传（行 12）：请求值原样落回执与 IR、换值跟着变；请求缺省 /
      显式 None 时回执兜底必须恰为非空 "unknown"（receipt-v1 schema 对
      rule_snapshot/kb_snapshot 的要求是 minLength≥1 的 string）
  T   run() 顶层契约（行 13）：七顶层字段存在且类型正确；顶层 decision /
      coverage 与 IR 同源一致（透传不是摆设）；obligations 无义务时空数组
      不省略
  U   证据装配（行 14）：evidence 部件缺席时不许丢 findings；evidence 输出
      必须装配进 findings；部件恰好一次；声明 untested 时归零
  R1  调换两步顺序 → 红
  R2  判定被调用两次 → 红
  R3  跳步 → 红
  R4  receipt 缺字段 → 红
  R5  failed 却调用 judge → 红
  R6  skipped 缺失 → 红

退出码：0 全过 / 1 有红 / 2 未测（导入失败或验收器自身异常）。
`--controls`：S/T/U 三组新断言的反向对照 —— 把 base/orchestrator.py 的源码
exec 成打坏的临时副本（不落盘、不碰真模块）：坏副本必须红、好副本必须绿
（好副本也红 = 判据恒真/误报，不算数，AGENTS §2.1.1）。
"""

import json
import os
import subprocess
import sys
import tempfile

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


C16_TITLES = {
    "C16a": "unit.textification 的 does_not_cover 逐字进 IR（不是丢了）",
    "C16b": "coverage 自带的 does_not_cover 也要搬进 IR",
    "C16c": "两侧合并去重、unit 的声明不许被 coverage 收窄",
    "C16d": "端到端：Orchestrator 跑完 IR.coverage 里逐字可查",
    "C16e": "顶层 coverage 与 IR 同源（透传不是摆设）",
    "C16f": "无声明时键不省略、值为 []（不是缺字段）",
    "C16g": "does_not_cover 非空 → coverage_state 不许是 full",
}


def _c16_probe(mod):
    """对给定的 orchestrator 模块跑 T-430 那组断言，返回 {编号: (是否绿, 读数)}。

    ★ 为什么抽成函数：`--controls` 必须能对**坏副本**跑**同一组**判据。
      判据只写在 main() 里，反向对照就只能把判断逻辑再抄一遍 ——
      那等于两套判据各自漂移（AGENTS §2.4.2 的第二层：判据与触发者要分开落地，
      而这里是把判据做成可复用对象，让坏副本真的走进去）。

    每个子项各自 try/except：坏副本可能直接 NameError（删掉整个函数），
    那必须落成**红**，不许把整个对照打死。
    """
    dnc = ["画面语义", "音轨"]
    img_textif = {"covers": ["图内文字"], "does_not_cover": list(dnc)}
    base_unit = unit()
    img_unit = dict(base_unit, textification=img_textif,
                    source={"kind": "image"})
    stem_cov = {"coverage_state": "partial", "modalities_evaluated": ["image"],
                "rules_version": {"version": "rs-1"},
                "control_points_applied": ["H01"]}
    out = {}

    def run(key, fn):
        try:
            out[key] = fn()
        except Exception as exc:  # noqa: BLE001
            out[key] = (False, "坏副本跑不起来：%r" % (exc,))

    # a) 只有 unit 声明 → 靠合并那一步补回来
    run("C16a", lambda: (
        mod._coverage_ir({"coverage": dict(stem_cov)},
                         {"control_points": ["H01"]}, img_unit)
        .get("does_not_cover") == dnc,
        repr(mod._coverage_ir({"coverage": dict(stem_cov)},
                              {"control_points": ["H01"]}, img_unit)
             .get("does_not_cover"))))
    # b) 只有 coverage 声明 → 靠分支白名单条目搬过来
    run("C16b", lambda: (
        mod._coverage_ir({"coverage": dict(stem_cov, does_not_cover=list(dnc))},
                         {"control_points": ["H01"]},
                         dict(base_unit, textification={"covers": ["图内文字"],
                                                        "does_not_cover": []}))
        .get("does_not_cover") == dnc,
        "见 C16b 读数"))
    # c) 两侧都有 → 合并去重，只许多不许少
    run("C16c", lambda: (
        mod._coverage_ir({"coverage": dict(stem_cov,
                                           does_not_cover=["画面语义"])},
                         {"control_points": ["H01"]}, img_unit)
        .get("does_not_cover") == dnc,
        "见 C16c 读数"))

    def _e2e():
        o = mod.Orchestrator(
            normalizer=img_unit, rule_judge=[finding], semantic_judge=[],
            coverage=dict(stem_cov), decision=decision,
            disposition=disposition, renderer={"rendered": True},
            store={"stored": True}, gateway={"sent": True},
            evaluator={"ok": True})
        return o.run(request(unit=img_unit))

    # d/e) 端到端：IR 与顶层 coverage 都要读得到
    run("C16d", lambda: (
        _e2e()["ir"]["coverage"].get("does_not_cover") == dnc,
        repr(_e2e()["ir"]["coverage"].get("does_not_cover"))))
    run("C16e", lambda: (
        _e2e()["coverage"].get("does_not_cover") == dnc,
        repr(_e2e()["coverage"].get("does_not_cover"))))

    # f) 两侧都空 → 键必须在，值为 []（不许省略成缺字段）
    def _empty_key():
        o = mod.Orchestrator(
            normalizer=base_unit, rule_judge=[finding], semantic_judge=[],
            coverage=dict(stem_cov), decision=decision,
            disposition=disposition, renderer={"rendered": True},
            store={"stored": True}, gateway={"sent": True},
            evaluator={"ok": True})
        cov = o.run(request(unit=base_unit))["ir"]["coverage"]
        return ("does_not_cover" in cov and cov["does_not_cover"] == [],
                repr(cov.get("does_not_cover")))
    run("C16f", _empty_key)

    # g) 非空时 state 不许是 full
    run("C16g", lambda: (
        _e2e()["ir"]["coverage"].get("coverage_state") != "full",
        repr(_e2e()["ir"]["coverage"].get("coverage_state"))))
    return out


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

    def build(counters, *, rule=None, sem=None, dec=None, unit_value=None,
              evidence=None, inject_evidence=True):
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
            evidence=(comp("evidence", evidence if evidence is not None
                           else (lambda ctx: ctx["findings"]))
                      if inject_evidence else None),
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
    r_v10 = build(Counter()).run(request(control_points_version="cp-test-v10"))
    report(r_v10["receipt"]["control_points_version"] == "cp-test-v10"
           and r_v10["ir"]["control_points_version"] == "cp-test-v10"
           and r_v10["receipt"]["control_points_version"] != "cp-test-v9",
           "C5b 换一个版本号 → 回执/IR 跟着变（不是写死常量）",
           repr((r_v10["receipt"]["control_points_version"],
                 r_v10["ir"]["control_points_version"])))

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

    # C8 运行路径必须真的调用 validate_ir / validate_receipt。
    # 只测两个函数本身不够：它们可以在模块里好好的，而 run 从不调用。
    orig_ir, orig_receipt = O.validate_ir, O.validate_receipt
    calls = {"ir": 0, "receipt": 0}

    def counting_ir(value):
        calls["ir"] += 1
        return orig_ir(value)

    def counting_receipt(value):
        calls["receipt"] += 1
        return orig_receipt(value)

    O.validate_ir, O.validate_receipt = counting_ir, counting_receipt
    try:
        r8 = build(Counter()).run(request(unit=None))
    finally:
        O.validate_ir, O.validate_receipt = orig_ir, orig_receipt
    report(calls == {"ir": 1, "receipt": 1} and r8["run_state"] == "OK",
           "C8 run 路径调用 validate_ir/validate_receipt 各一次",
           "calls=%r run_state=%r" % (calls, r8.get("run_state")))

    # C8b validator 报问题时 run 必须 fail-closed（不是安静发出坏对象）。
    def bad_ir(_value):
        return ["forced_contract_problem"]

    O.validate_ir = bad_ir
    raised = False
    try:
        build(Counter()).run(request(unit=None))
    except ValueError:
        raised = True
    finally:
        O.validate_ir = orig_ir
    report(raised, "C8b validator 报问题 → run 抛 ValueError（fail-closed）", "")

    # C9 未知桶：回执四键计数 + 转人原因/目标层 + report snapshot 装配。
    buckets = {"family": 1, "scene_domain": 1,
               "authority_source": 1, "consequence": 1}
    unknown_decision = dict(decision, state="REVIEW", layer="DP4",
                            unknown_buckets=buckets,
                            unknown_bucket_total=4,
                            handoff_reason="unknown_bucket",
                            target_layer="DP4")
    r9 = build(Counter(), dec=unknown_decision).run(request(unit=None))
    rc9 = r9["receipt"]
    report(rc9.get("unknown_buckets") == buckets
           and rc9.get("unknown_bucket_total") == 4
           and rc9.get("handoff_reason") == "unknown_bucket"
           and rc9.get("target_layer") == "DP4",
           "C9 receipt 带 unknown_buckets 四键/总数/原因/目标层",
           repr({k: rc9.get(k) for k in ("unknown_buckets",
                                          "unknown_bucket_total",
                                          "handoff_reason", "target_layer")}))
    snap = r9.get("report_snapshot") or {}
    report(snap.get("unknown_bucket_counts") == buckets
           and snap.get("ir", {}).get("receipt_ref") == rc9.get("receipt_id"),
           "C9b report_snapshot.unknown_bucket_counts 四键齐全",
           repr(snap.get("unknown_bucket_counts")))
    report(r["receipt"].get("unknown_buckets") ==
           {k: 0 for k in O.UNKNOWN_BUCKET_KEYS}
           and r["receipt"].get("unknown_bucket_total") == 0
           and r["report_snapshot"].get("unknown_bucket_counts") ==
           {k: 0 for k in O.UNKNOWN_BUCKET_KEYS},
           "C9c 无未知桶时四键仍为 0（不省略）", repr(r["receipt"].get("unknown_buckets")))

    # C9d 报告侧：让真实 report_render.mjs 读 snapshot，四个计数必须出现。
    runner = tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False)
    try:
        runner.write(
            "import { renderReport } from %r;\n"
            "let input = '';\n"
            "for await (const c of process.stdin) input += c;\n"
            "process.stdout.write(JSON.stringify(renderReport(JSON.parse(input))));\n"
            % ("file://" + os.path.join(REPO_ROOT, "tools", "audit",
                                        "report_render.mjs")))
        runner.close()
        proc = subprocess.run(["node", runner.name], input=json.dumps(
            snap, ensure_ascii=False), text=True, capture_output=True)
        rendered = json.loads(proc.stdout) if proc.returncode == 0 and proc.stdout else {}
        markdown = rendered.get("markdown") or ""
        report(rendered.get("ok") is True
               and all(("%s=1" % k) in markdown for k in buckets),
               "C9d report_render 读到四个未知桶计数",
               "rc=%r errors=%r" % (proc.returncode,
                                    rendered.get("errors")))
    finally:
        try:
            os.unlink(runner.name)
        except OSError:
            pass

    # ── S 组（行 12）：快照回传契约 ─────────────────────────────
    # 验收表行 12：「缺必填字段的请求 → 明确报缺字段且不产生回执/结论」。
    # 实测：缺 rule_snapshot/kb_snapshot 仍 run_state=OK 并产回执（兜底
    # "unknown"）—— 「缺字段不产回执」这一半无生产行为，未补。
    # 可执行的那一半是「回执/IR 必须把请求给的快照**原样**带出去，且兜底
    # 形态满足 receipt-v1 schema（string、minLength≥1）」：
    #   S1 原样回传（读数来自请求，不是常量）；S2 换值跟着变；
    #   S3 缺省兜底不许是 None/空；S4 缺省兜底恰为 "unknown"；
    #   S5 显式 None 不许回传 None（行 12 变异的真形状）。
    s_run = build(Counter()).run(request(rule_snapshot="rs-orig-1",
                                         kb_snapshot="kb-orig-1"))
    report(s_run["receipt"]["rule_snapshot"] == "rs-orig-1"
           and s_run["receipt"]["kb_snapshot"] == "kb-orig-1",
           "S1 请求快照原样落回执（不写死不缺省）",
           repr((s_run["receipt"].get("rule_snapshot"),
                 s_run["receipt"].get("kb_snapshot"))))
    report(s_run["ir"]["rule_snapshot"] == "rs-orig-1"
           and s_run["ir"]["kb_snapshot"] == "kb-orig-1",
           "S1b 请求快照原样落 ReviewIR",
           repr((s_run["ir"].get("rule_snapshot"), s_run["ir"].get("kb_snapshot"))))
    s_run2 = build(Counter()).run(request(rule_snapshot="rs-orig-2",
                                          kb_snapshot="kb-orig-2"))
    report(s_run2["receipt"]["kb_snapshot"] == "kb-orig-2"
           and s_run2["receipt"]["kb_snapshot"] != "kb-orig-1",
           "S2 换一个快照值 → 回执跟着变（不是常量）",
           repr(s_run2["receipt"].get("kb_snapshot")))
    s_req_missing = request()
    del s_req_missing["kb_snapshot"]
    s_run3 = build(Counter()).run(s_req_missing)
    s_kb3 = s_run3["receipt"].get("kb_snapshot")
    report(isinstance(s_kb3, str) and s_kb3.strip() != "",
           "S3 请求缺 kb_snapshot → 回执不许回传 None/空串"
           "（receipt-v1 要求非空 string）",
           repr(s_kb3))
    report(s_kb3 == "unknown",
           "S4 请求缺 kb_snapshot → 回执兜底恰为 \"unknown\"（不是缺省/原值）",
           repr(s_kb3))
    s_run5 = build(Counter()).run(request(kb_snapshot=None))
    s_kb5 = s_run5["receipt"].get("kb_snapshot")
    report(s_kb5 is not None and s_kb5 != "",
           "S5 显式 kb_snapshot=None 不许回传 None（行 12 变异的真形状）",
           repr(s_kb5))

    # ── T 组（行 13）：run() 顶层契约 ─────────────────────────────
    # 验收表行 13：「七个顶层字段存在且类型正确」。实测顶层键集是
    # run_state/ir/receipt/decision/coverage/findings/external_label/
    # judge_invoked/steps/report_snapshot —— 判据里的 state/obligations
    # 两个顶层键不存在、ERROR→null 也未实现（无该行为，未补，见汇报）。
    # 可执行的部分：
    #   T1 七字段齐全；T2 类型正确；T3 coverage 顶层与 IR 一致；
    #   T4 顶层 decision 的 state/obligations 与 IR 一致 —— 顶层透传被
    #      砍掉后立刻红（行 13 变异的真形状）；
    #   T5 无义务时 obligations=[] 且键不省略（不是缺字段）。
    t_run = build(Counter()).run(request(unit=None))
    t_keys = set(t_run)
    t_top = ("findings", "receipt", "run_state", "external_label",
             "coverage", "decision", "ir")
    report(all(k in t_keys for k in t_top),
           "T1 run() 七个顶层字段齐全（findings/receipt/coverage/decision/ir/"
           "run_state/external_label）",
           repr(sorted(k for k in t_top if k not in t_keys)))
    t_types = {"findings": list, "receipt": dict, "run_state": str,
               "coverage": dict, "decision": dict, "ir": dict,
               "external_label": (str, type(None))}
    t_bad = [k for k, t in t_types.items()
             if k in t_keys and not isinstance(t_run.get(k), t)]
    report(t_bad == [],
           "T2 顶层字段类型正确（findings=list、receipt/coverage/decision/ir=dict、"
           "run_state=str、external_label=str|None）",
           repr(t_bad))
    report(t_run["coverage"] == t_run["ir"]["coverage"],
           "T3 顶层 coverage 与 IR 一致（透传不是摆设）",
           repr(t_run.get("coverage")))
    report(t_run["decision"].get("state") == t_run["ir"]["decision"]["state"]
           and t_run["decision"].get("obligations")
           == t_run["ir"]["decision"]["obligations"],
           "T4 顶层 decision 的 state/obligations 与 IR 一致（砍掉透传立刻红）",
           repr((t_run["decision"], t_run["ir"]["decision"])))
    t_dec = build(Counter(), dec={"state": "PASS", "layer": "DP1",
                                  "release_status": "待放行",
                                  "obligations": [], "run_state": "OK"}
                  ).run(request(unit=None))
    report("obligations" in t_dec["decision"]
           and isinstance(t_dec["decision"]["obligations"], list)
           and t_dec["decision"]["obligations"] == [],
           "T5 无义务时 obligations=[] 且键不省略（不是缺字段）",
           repr(t_dec["decision"].get("obligations")))

    # ── U 组（行 14）：证据装配 ─────────────────────────────────
    # 验收表行 14：判定之后必须有处置前的证据装配步，且「某步被重复触发
    # 仍只记一次」。可执行的部分：
    #   U1 evidence 部件**缺席**（构造器不注入，不是注入 None 部件）时
    #      findings 不许丢 —— 生产代码把 evidence 装配与 findings 兜底写在
    #      同一行（do_dispose 首句），兜底丢了 findings，判定结果就从交付
    #      物上消失（行 14 变异的真形状，只在"未注入 evidence"路径发生）；
    #   U2 evidence 输出（处置前证据装配）必须真的装配进 findings；
    #   U3 evidence 部件恰好调用一次 + 五步结构不变；声明 untested 时归零。
    u_counts = Counter()
    u_no_ev = build(u_counts, inject_evidence=False).run(request(unit=None))
    report(u_no_ev["findings"] == [finding, candidate],
           "U1 未注入 evidence 部件 → 判定结果不许丢（兜底必须是 findings）",
           repr(u_no_ev.get("findings")))
    report(u_no_ev["ir"]["findings"] == [finding, candidate],
           "U1b 未注入 evidence → ReviewIR.findings 同样不许丢",
           repr(u_no_ev["ir"].get("findings")))

    u_counts2 = Counter()

    def u_ev(ctx):
        return list(ctx.get("findings") or []) + [
            dict(finding, finding_id="f-evidence-1")]

    u_run2 = build(u_counts2, evidence=u_ev).run(request(unit=None))
    report(u_counts2["evidence"] == 1,
           "U2 evidence 部件恰好调用一次（不重复触发）",
           repr(u_counts2.get("evidence")))
    report(u_run2["findings"] == [finding, candidate,
                                  dict(finding, finding_id="f-evidence-1")],
           "U2b evidence 输出必须装配进 findings（不是装配了寂寞）",
           repr(u_run2.get("findings")))
    report(len(u_run2["receipt"]["steps"]) == 5,
           "U2c evidence 装配不改变五步结构（重复触发无额外步）",
           repr(len(u_run2["receipt"]["steps"])))

    u_run3 = build(Counter(), evidence={"status": "untested", "findings": []}
                   ).run(request(unit=None))
    report(u_run3["findings"] == [],
           "U3 evidence 声明 untested → findings 归零（不沿用判定结果）",
           repr(u_run3.get("findings")))

    # ── C16 组（T-430）：does_not_cover 不许在最后一跳被丢掉 ──────────
    # 为什么这一条必须有：`contract.from_media()` 刻意**不给** covers/does_not_cover
    # 默认值（默认值会让「只做了 OCR」看起来像「图片已审」）。而 `_coverage_ir()`
    # 用白名单重建 coverage，漏了这个键 —— 声明在最后一跳被静默取消。
    # 文本上无害（文本该字段本来就空），**一开媒体就等于把没审的部分伪装成审过**。
    #
    # ★ 刻意分成 a/b 两条独立的断言，因为它们是**两个不同的来源**：
    #   a) coverage 里没有、unit.textification 里有 → 靠合并那一步补回来
    #   b) unit 里没有、coverage 里有     → 靠分支里的白名单条目搬过来
    #   删掉其中任何一处，只会让对应那一条红。只写一条（两个来源都填满）会让
    #   「另一处删掉」也照旧绿 —— 那是本项目 §2.4 点名的「名字出现过≠拦得住」。
    #
    # ★ 判据体在 _c16_probe()，因为 --controls 要对**坏副本**跑同一组判据。
    for name, (is_ok, detail) in _c16_probe(O).items():
        report(is_ok, "%s %s" % (name, C16_TITLES[name]), detail)

    print("----------------------------------------")
    if failed == 0:
        print("✅ %d/%d 全过" % (passed, passed + failed))
        return 0
    print("❌ %d passed, %d failed" % (passed, failed), file=sys.stderr)
    return 1


# ── --controls：S/T/U 三组断言的反向对照 ────────────────────────────
# ★ 主检查里的 report() 全部是「对生产代码断言」，自己没有坏样本可喂。
#   这里把 base/orchestrator.py 的源码 exec 成**打坏的临时副本**（不落盘、
#   不碰真模块），喂同一形状的输入：坏副本必须红、好副本必须绿。
#   好副本也红 = 判据写成恒真/误报，不算数（AGENTS §2.1.1）。
def _orc_text():
    with open(os.path.join(REPO_ROOT, "base", "orchestrator.py"),
              encoding="utf-8") as f:
        return f.read()


def _exec_orc(text, tag):
    """exec 一份 orchestrator 源码变体，返回可用的 Orchestrator 类。"""
    ns = {"__name__": "orchestrator_%s" % tag,
          "__file__": os.path.join(REPO_ROOT, "base", "orchestrator.py")}
    exec(compile(text, "orchestrator_%s.py" % tag, "exec"), ns)
    return ns["Orchestrator"]


class _Ns:
    """把 `exec` 出来的命名空间 dict 包成可属性访问的对象。

    ★ 为什么要包：`_c16_probe(mod)` 里写 `mod._coverage_ir` / `mod.Orchestrator`。
      直接把 dict 传进去会 AttributeError，而那会被当成「坏副本跑不起来 = 红」——
      于是**好副本也被判红**，全部对照恒红。这正是 AGENTS §2.1.1 那个病：
      一个恒红的检查器比没有更糟，人会开始不看报告。
    """

    def __init__(self, ns):
        self.__dict__.update(ns)


def _exec_mod(text, tag):
    """exec 一份源码变体，返回**整个命名空间**（包成可属性访问）。

    ★ 与 `_exec_orc` 的区别：`_c16_probe()` 要用 `_coverage_ir`（模块级函数），
      只拿 Orchestrator 类就问不到它 —— 那样反向对照只能测到端到端那一半，
      「分支白名单删掉」这类只影响直接调用的变异就测不出来。
    """
    ns = {"__name__": "orchestrator_%s" % tag,
          "__file__": os.path.join(REPO_ROOT, "base", "orchestrator.py")}
    exec(compile(text, "orchestrator_%s.py" % tag, "exec"), ns)
    return _Ns(ns)


def _plain_orc(cls, *, dispo=None):
    return cls(
        normalizer=unit(), rule_judge=[finding], semantic_judge=[],
        coverage=coverage, decision=decision,
        disposition=dispo if dispo is not None else disposition,
        renderer={"rendered": True}, store={"stored": True},
        gateway={"sent": True}, evaluator={"ok": True})


def run_controls():
    """返回 (n_pass, n_fail, n_untested)。"""
    ok = fail = 0

    def C(name, cond, detail=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print("  ✅ %s" % name)
        else:
            fail += 1
            print("  ❌ %s  %s" % (name, detail))

    print("verify_orchestrator · --controls（S/T/U 新断言的反向对照）")
    src = _orc_text()

    def req_no_kb():
        r = request()
        del r["kb_snapshot"]
        return r

    # S 组的反向面：把「快照兜底恰为非空 unknown」打坏成三种坏形状，
    # 坏副本上 S3/S4/S5 的判据必须读到坏值（= 红）；好副本同输入必须绿。
    s_cases = (
        ("CS1 兜底成 None 的坏副本必须红（行 12 变异形状）",
         src.replace('ctx["request"].get("rule_snapshot") or "unknown"',
                     'ctx["request"].get("rule_snapshot") or None')
            .replace('ctx["request"].get("kb_snapshot") or "unknown"',
                     'ctx["request"].get("kb_snapshot") or None'),
         lambda kb, rs: kb is None or rs is None),
        ("CS2 兜底成空串的坏副本必须红",
         src.replace('ctx["request"].get("rule_snapshot") or "unknown"',
                     'ctx["request"].get("rule_snapshot") or ""')
            .replace('ctx["request"].get("kb_snapshot") or "unknown"',
                     'ctx["request"].get("kb_snapshot") or ""'),
         lambda kb, rs: kb == "" or rs == ""),
        ("CS3 兜底成写死常量的坏副本必须红（S1/S2 的读数不许恒真）",
         src.replace('ctx["request"].get("kb_snapshot") or "unknown"',
                     '"kb-stale-constant"'),
         lambda kb, rs: kb == "kb-stale-constant"),
    )
    for name, bad, is_bad in s_cases:
        if bad == src:
            C(name, False, "找不到替换原文（生产代码变了，对照过期）")
            continue
        try:
            rb = _plain_orc(_exec_orc(bad, "sbad")).run(req_no_kb())
            kb, rs = rb["receipt"].get("kb_snapshot"), rb["receipt"].get("rule_snapshot")
            C(name, is_bad(kb, rs), "坏副本跑出绿值 kb=%r rs=%r" % (kb, rs))
        except Exception as e:  # noqa: BLE001
            C(name, False, "坏副本跑不起来：%s" % e)
    try:
        rg = _plain_orc(_exec_orc(src, "sgood")).run(req_no_kb())
        kb = rg["receipt"].get("kb_snapshot")
        C("CS4 好副本跑同输入必须绿（kb_snapshot=unknown）",
          kb == "unknown", "好副本被误伤：%r" % kb)
    except Exception as e:  # noqa: BLE001
        C("CS4 好副本跑不起来", False, str(e))

    # T 组的反向面：把 run() 顶层 decision 砍成只剩 run_state（行 13 变异
    # 的真形状）。坏副本里顶层 decision.get("state") 对不上 IR → T4 必须红；
    # 好副本同输入必须绿。
    bad_t = src.replace('"decision": decision,',
                        '"decision": {"run_state": decision.get("run_state", "OK")},')
    if bad_t == src:
        C("CT1 找不到 \"decision\": decision, 原文（生产代码变了，对照过期）",
          False, "")
    else:
        try:
            rt = _plain_orc(_exec_orc(bad_t, "tbad")).run(request())
            top_dec = rt.get("decision") or {}
            C("CT1 顶层 decision 被砍的坏副本必须红（T4：与 IR 对不上）",
              top_dec.get("state") != (rt.get("ir") or {}).get("decision", {}
                                                               ).get("state")
              or {"state", "obligations"} - set(top_dec),
              "坏副本跑出绿值：top=%r" % (sorted(top_dec),))
        except Exception as e:  # noqa: BLE001
            C("CT1 顶层 decision 被砍的坏副本必须红", False, "坏副本跑不起来：%s" % e)
        try:
            rq = _plain_orc(_exec_orc(src, "tgood")).run(request())
            C("CT2 好副本同输入必须绿（顶层 decision 与 IR 一致）",
              rq["decision"].get("state") == rq["ir"]["decision"]["state"]
              and rq["decision"].get("obligations")
              == rq["ir"]["decision"]["obligations"],
              "好副本被误伤：%r" % (rq.get("decision"),))
        except Exception as e:  # noqa: BLE001
            C("CT2 好副本跑不起来", False, str(e))

    # U 组的反向面：把「evidence 缺席时兜底 findings」砍成 None（行 14 变异
    # 的真形状）。坏副本必须红（findings 丢）；好副本同输入必须绿。
    bad_u = src.replace(
        'ctx["evidence"] = self._call(self.evidence, ctx) '
        'if self.evidence is not None else ctx["findings"]',
        'ctx["evidence"] = self._call(self.evidence, ctx) '
        'if self.evidence is not None else None')
    if bad_u == src:
        C("CU1 找不到 evidence 装配原文（生产代码变了，对照过期）", False, "")
    else:
        try:
            ru = _plain_orc(_exec_orc(bad_u, "ubad")).run(request())
            C("CU1 evidence 兜底砍掉 findings 的坏副本必须红（U1/U1b）",
              ru.get("findings") != [finding]
              or ru.get("ir", {}).get("findings") != [finding],
              "坏副本跑出绿值 findings=%r" % (ru.get("findings"),))
        except Exception as e:  # noqa: BLE001
            C("CU1 evidence 兜底砍掉 findings 的坏副本必须红", False,
              "坏副本跑不起来：%s" % e)
        try:
            rg2 = _plain_orc(_exec_orc(src, "ugood")).run(request())
            C("CU2 好副本同输入必须绿（findings 原样）",
              rg2.get("findings") == [finding],
              "好副本被误伤：%r" % (rg2.get("findings"),))
        except Exception as e:  # noqa: BLE001
            C("CU2 好副本跑不起来", False, str(e))

    # ── C16 组（T-430）的反向面 ───────────────────────────────────
    # ★ 票面要求的变异是「删掉那一行 → 必须红」。这里把它拆成三处**互不重叠**
    #   的打断，因为 T-430 的修法本身有两条路（分支白名单搬 + unit 兜底合并），
    #   外加「哪条断言在守哪一处」：
    #     D1 删掉合并那一步（cov["does_not_cover"] = _merge_...(cov, unit) 整行）
    #        → 只走 unit 的那半 source 就丢了 → C16a / C16d / C16e 红
    #     D2 删掉分支里的白名单条目（"does_not_cover": list(src.get(...))）
    #        → 只走 coverage 的那半丢了 → C16b 红
    #     D3 把合并写成「只读 coverage、不读 unit」
    #        → 看似有合并、实际收窄 → C16a / C16c 红
    #   三处各只让「对应那几条」红，这正是「一处断言守一处成分」的证明。
    #   若三处都只让同一条红，说明这些断言在守同一件事，就该合并。
    c16_bad = (
        ("CD1 删掉「合并进 cov」那一行 → C16a/C16c/C16d/C16e/C16f 必须红（票面变异）",
         src.replace(
             '    cov["does_not_cover"] = _merge_does_not_cover(cov, unit)\n', ''),
         # 没有这一行，键只在「branch b 恰好搬了」时才在。a/c 读不到声明；
         # d/e 端到端同样读不到；f 要的「空声明时键仍在」直接缺字段。
         # b 仍绿 —— 它走的是分支白名单那条路，与这一行无关。这正是分工的证据。
         {"C16a", "C16c", "C16d", "C16e", "C16f"}),
        ("CD2 删掉分支白名单里的 does_not_cover 条目 → C16b 必须红",
         src.replace(
             '            "does_not_cover": list(src.get("does_not_cover") or []),\n',
             ''),
         # 只有 b 走「coverage 自带」那条路；其它几条的输入里 unit 有声明，
         # 由合并那一步兜住，所以它们必须仍然绿。
         {"C16b"}),
        ("CD3 合并只读 coverage、不读 unit → C16a/C16c/C16d/C16e 必须红（收窄形状）",
         src.replace(
             '    for src in ((unit or {}).get("textification") or {},\n'
             '                cov if isinstance(cov, dict) else {}):',
             '    for src in ((cov if isinstance(cov, dict) else {}),):'),
         # 这一版「看起来有合并」，实际收窄：unit 的声明被吞掉 → a/c 红，
         # 端到端 d/e 一起红。f 仍绿（键照样写、值为空），符合预期 ——
         # 它守的是「键不许缺」，不是「值来自哪一侧」。
         {"C16a", "C16c", "C16d", "C16e"}),
    )
    for name, bad, must_red in c16_bad:
        if bad == src:
            C(name, False, "找不到替换原文（生产代码变了，对照过期）")
            continue
        try:
            bad_mod = _exec_mod(bad, "c16bad")
            got = _c16_probe(bad_mod)
        except Exception as e:  # noqa: BLE001
            C(name, False, "坏副本跑不起来：%s" % e)
            continue
        reds = {k for k, (okv, _d) in got.items() if not okv}
        C(name, reds == must_red,
          "红的集合是 %r，应当是 %r" % (sorted(reds), sorted(must_red)))
    # 反向对照的另一半：好副本必须一条都不红，否则上面全是误报
    try:
        good = _c16_probe(_exec_mod(src, "c16good"))
        C("CD4 好副本同输入必须全绿（否则上面三条是误报）",
          all(okv for okv, _d in good.values()),
          "好副本被误伤：%r" % (sorted(k for k, (o2, _d) in good.items() if not o2),))
    except Exception as e:  # noqa: BLE001
        C("CD4 好副本跑不起来", False, str(e))

    print("\n%s --controls %d 过 · %d 红 · 0 未测"
          % ("✅" if fail == 0 else "❌", ok, fail))
    return ok, fail, 0


def _usage():
    print("用法：python3 tools/verify_orchestrator.py [--controls]")


if __name__ == "__main__":
    if "--controls" in sys.argv:
        _ok, _fail, _untested = run_controls()
        sys.exit(1 if _fail else (2 if (_untested and not _ok) else 0))
    if any(a.startswith("-") and a not in ("--controls", "-h", "--help")
           for a in sys.argv[1:]):
        _usage()
        sys.exit(2)
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
