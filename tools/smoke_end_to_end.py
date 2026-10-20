#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""smoke_end_to_end.py —— 第 1 阶段出门冒烟（真实模块，不写仓内）

链路：
  submission_router → normalizer → rule_judge → evidence_sync →
  coverage_composer → decision_table → disposition_router →
  orchestrator（组装 ReviewIR + receipt）→ report_render（Node）→
  report_store（静态落盘 + ACL 回读）→ send_gateway（形态决策）

断言：
  - ReviewIR 含 findings / decision / coverage / receipt；
  - 报告文件六区块齐全；
  - 群消息一句 + 报告链接；
  - release_status=待放行；receipt.skipped=[]；
  - 产物只落临时目录，不写仓内。

反向对照：
  - 把 decision_table 换成「返回 PASS」的桩，但 coverage=partial：
    smoke 的一致性守卫必须拒绝产出报告（partial 永不 PASS），
    证明主链路不是靠桩通过的。

退出码：0 全过 / 1 有红 / 2 未测（Node 不可用、临时目录建不出等）。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "base"))
sys.path.insert(0, ROOT)

TEXT = "这款产品可以治疗疾病，疗效显著。"
SKILL_ID = "skill-smoke"
SKILL_VERSION = "1.0.0"
SKILL_HASH = "a" * 64
RULE_SNAPSHOT = "rs-smoke-1"
KB_SNAPSHOT = "kb-smoke-1"

FAILS = []
CHECKS = 0


def T(cid, ok, detail=""):
    global CHECKS
    CHECKS += 1
    if not ok:
        FAILS.append("%s  %s" % (cid, detail))


def consistency_errors(result):
    """独立于 decision_table 桩的出门守卫。"""
    errs = []
    d = result.get("decision") or {}
    cov = result.get("coverage") or {}
    if cov.get("coverage_state") != "full" and d.get("state") == "PASS":
        errs.append("partial_never_pass")
    if d.get("release_status") != "待放行":
        errs.append("release_status_not_pending")
    if (result.get("receipt") or {}).get("skipped") != []:
        errs.append("skipped_not_empty")
    if d.get("run_state") != "OK":
        errs.append("decision_run_state_not_ok")
    return errs


def main():
    if not shutil.which("node"):
        print("⚠ 未测：找不到 node —— 不是通过")
        return 2
    try:
        TMP = tempfile.mkdtemp(prefix="smoke_e2e_")
    except OSError as e:
        print("⚠ 未测：建不出临时目录（%s）" % e)
        return 2

    try:
        from base import submission_router as SR
        from base import normalizer as N
        from base import coverage_composer as CC
        from base import orchestrator as O
        from base import decision_table as DT
        from base import send_gateway as SG
        from base.control_points import ControlPointRegistry
        from base.evidence_sync import enrich_findings
        from base.rule_judge import RuleJudge
        from base.disposition_router import DispositionRouter
        from base.report_store import ReportStore
    except Exception as e:  # noqa: BLE001
        print("❌ 导入链路模块失败：%s" % e)
        return 1

    reg = ControlPointRegistry()
    judge = RuleJudge(reg)
    disp = DispositionRouter()
    store = ReportStore(os.path.join(TMP, "data"), "https://static.example.com")

    unit = N.normalize(
        {"kind": "free_text", "text": TEXT, "uri": "inline:smoke"},
        covers=["正文"], does_not_cover=[])

    hits = judge.judge(unit)
    T("S1 rule_judge 对样本有 P0 命中", len(hits) > 0, "n=%d" % len(hits))
    T("S2 命中 quote == 原文切片",
      all(h["quote"] == TEXT[h["start"]:h["end"]] for h in hits), str(hits)[:200])

    def drafts():
        out = []
        for i, h in enumerate(hits):
            cp = reg.get_active(h["control_code"])
            refs = cp.get("authority_ref") or [{}]
            ref = refs[0]
            out.append({
                "finding_id": "f%d" % (i + 1),
                "control_code": h["control_code"],
                # ★ 2026-10-20 补：`judge()` 的 HIT_FIELDS 本来就含 `rule_key`
                #   （`base/rule_judge.py:40-42`），而这里原来只搬 control_code / severity /
                #   quote / location，**把 rule_key 丢了** —— 下游 `evidence_sync` 是
                #   `out = dict(finding)` 整体复制，丢在这一跳就再也恢复不了。
                #   后果：finding 只能追到「哪一类控制点」，追不到「哪条检测规则」，
                #   而 control_code 并不唯一（26 条规则里 H01/H02/H05/M03/M04 各挂 2 条）。
                "rule_key": h["rule_key"],
                "status": "confirmed",
                "severity": h["severity"],
                "produced_by": "rule",
                "detected_by": "P0",
                "derived_from": None,
                "confirmed_by_rule_class": False,
                "quote": h["quote"],
                "location": {"type": "text", "start": h["start"], "end": h["end"]},
                "authority_ref": [{"ref_id": ref.get("entry_id") or ref.get("article") or "REF-1"}],
            })
        return out

    def query(ref):
        return {"state": "ok", "reason": "fixture"}

    request = {
        "skill_id": SKILL_ID,
        "skill_version": SKILL_VERSION,
        "skill_hash": SKILL_HASH,
        "rule_snapshot": RULE_SNAPSHOT,
        "kb_snapshot": KB_SNAPSHOT,
        "control_points": ["H01"],
        "control_points_by_family": {"宣称控制": "ran"},
        "modalities_evaluated": ["free_text"],
        "rules_version": {"version": "rs-smoke", "fingerprint": "f" * 16},
        "covers": ["正文"],
        "does_not_cover": [],
        "parse_status": "ok",
        "raw_input": {"kind": "free_text", "text": TEXT, "uri": "inline:smoke"},
    }

    def build(decision_override=None):
        def cov(ctx):
            return CC.compose_and_derive(
                modalities_evaluated=["free_text"],
                rules_version={"version": "rs-smoke", "fingerprint": "f" * 16},
                control_points_by_family={"宣称控制": "ran"},
                not_run_reasons=[],
                does_not_cover=[],
                parse_status="ok")

        def decision(ctx):
            if decision_override is not None:
                return decision_override
            return DT.decide({
                "parse_status": ctx["unit"].get("parse_status", "ok"),
                "failure_kind": ctx["unit"].get("failure_kind"),
                "coverage_state": ctx["coverage"].get("coverage_state"),
                "findings": ctx["findings"],
            })

        def evidence(ctx):
            return enrich_findings(
                ctx["findings"], query, RULE_SNAPSHOT, KB_SNAPSHOT)["findings"]

        def disposition(ctx):
            return disp.route(ctx["decision"], ctx["receipt_id"])

        return O.Orchestrator(
            normalizer=lambda ctx: unit,
            rule_judge=lambda ctx: drafts(),
            evidence=evidence,
            coverage=cov,
            decision=decision,
            disposition=disposition,
        )

    # ── 主链路 ──────────────────────────────────────────────────────
    router = SR.SubmissionRouter()
    submission = {
        "submission_id": "sub-smoke-1",
        "content_type": "文本",
        "content_stage": "brief",
        "entry_channel": "群消息",
        "source": {"kind": "free_text"},
    }
    verdict = SR.classify_submission(submission)
    T("S3 submission_router 受理样本", verdict.get("outcome") == "accepted", str(verdict))

    result = build().run(request)
    ir, receipt, decision = result["ir"], result["receipt"], result["decision"]

    # 联调导出：只写到 SMOKE_DUMP_IR 指定的临时目录，不写仓内。
    dump = os.environ.get("SMOKE_DUMP_IR")
    if dump:
        os.makedirs(dump, exist_ok=True)
        with open(os.path.join(dump, "ir.json"), "w", encoding="utf-8") as f:
            json.dump(ir, f, ensure_ascii=False, indent=2)
        case = {
            "case_id": "case-smoke",
            "tenant": "t1",
            "product_line": "pump",
            "submitter_id": "u_sub",
            "final_reviewer_id": "u_dp3",
            "assignee_id": "u_dp3",
            "actionable": True,
            "ir": ir,
        }
        with open(os.path.join(dump, "cases.json"), "w", encoding="utf-8") as f:
            json.dump([case], f, ensure_ascii=False, indent=2)

    attempt = router.submit(submission, ir_id=ir["ir_id"], receipt_id=receipt["receipt_id"])
    T("S4 Attempt 落账且 outcome=accepted", attempt.get("outcome") == "accepted", str(attempt))
    T("S5 五步各一次", result.get("steps") == list(O.STEP_ORDER), str(result.get("steps")))
    T("S5b 五步顺序逐字正确",
      result.get("steps") == ["normalize", "judge", "dispose", "output", "evaluate"],
      str(result.get("steps")))

    T("S6 ReviewIR 必备字段齐全", all(k in ir for k in O.REQUIRED_IR_FIELDS),
      str([k for k in O.REQUIRED_IR_FIELDS if k not in ir]))
    T("S7 IR 含 findings/decision/coverage/receipt_ref",
      isinstance(ir["findings"], list) and ir["findings"]
      and isinstance(ir["decision"], dict) and isinstance(ir["coverage"], dict)
      and ir["receipt_ref"] == receipt["receipt_id"], "")
    T("S8 结论 BLOCK / DP2", decision.get("state") == "BLOCK" and decision.get("layer") == "DP2",
      "%s / %s" % (decision.get("state"), decision.get("layer")))
    T("S9 release_status=待放行", decision.get("release_status") == "待放行", str(decision.get("release_status")))
    T("S10 receipt.skipped=[]", receipt.get("skipped") == [], str(receipt.get("skipped")))
    T("S11 覆盖证明 partial（空族）", result["coverage"].get("coverage_state") == "partial",
      str(result["coverage"].get("coverage_state")))
    T("S12 主链路一致性守卫零错误", consistency_errors(result) == [], str(consistency_errors(result)))
    T("S13 真实 decision_table 复算与 IR 决策一致",
      DT.decide({
          "parse_status": "ok", "failure_kind": None,
          "coverage_state": "partial", "findings": ir["findings"],
      }).get("state") == ir["decision"]["state"], "")

    # ── report_render（Node） ──────────────────────────────────────
    runner = os.path.join(TMP, "render_runner.mjs")
    render_mod = "file://" + os.path.join(ROOT, "tools", "audit", "report_render.mjs")
    with open(runner, "w", encoding="utf-8") as f:
        f.write(
            "import { renderReport, renderMessage } from %r;\n"
            "let input = '';\n"
            "for await (const c of process.stdin) input += c;\n"
            "const snap = JSON.parse(input);\n"
            "const mode = process.argv[2];\n"
            "const out = mode === 'report' ? renderReport(snap) : renderMessage(snap);\n"
            "process.stdout.write(JSON.stringify(out));\n" % render_mod)

    def render(mode, snapshot):
        p = subprocess.run(["node", runner, mode], input=json.dumps(snapshot, ensure_ascii=False),
                           text=True, capture_output=True)
        if p.returncode != 0:
            return {"ok": False, "errors": ["node_rc=%d:%s" % (p.returncode, p.stderr[-300:])]}
        try:
            return json.loads(p.stdout)
        except ValueError:
            return {"ok": False, "errors": ["bad_node_json:%s" % p.stdout[:200]]}

    base_snapshot = {
        "ir": ir,
        "failure_kind_counts": {"fetch_error": 0, "parse_error": 0, "empty": 0, "unsupported": 0},
        "unknown_bucket_counts": {},
        "evidence": [],
        "unassessed": [],
        "receipt": {
            "skill": SKILL_ID, "version": SKILL_VERSION, "fingerprint": SKILL_HASH,
            "skipped_steps": "无", "rule_snapshot": RULE_SNAPSHOT,
        },
    }
    rep = render("report", base_snapshot)
    T("S14 report_render 生成报告", rep.get("ok") is True, str(rep.get("errors"))[:300])
    md = rep.get("markdown") or ""
    for title in ("## 结论", "## 命中的问题", "## 覆盖证明",
                  "## 依据清单", "## 未审说明", "## 执行回执"):
        T("S15 报告含六区块：%s" % title, title in md, "")
    T("S16 报告结论非 PASS", "状态：BLOCK" in md and "状态：PASS" not in md, "")

    # report_store：直接落渲染器输出（R1 已由渲染器产出，不再补 front matter）
    pub = store.publish(
        ir, lambda _ir: md,
        {"tenant": "t1", "product_line": "p1", "submitter_id": "u1", "assigned": []},
        now="2026-10-19T00:00:00Z")
    T("S17 report_store 发布成功", pub.get("ok") is True, str(pub))
    rpath = os.path.join(store.root, pub.get("path", ""))
    T("S17b 落盘内容与渲染器输出逐字相同（无落盘前补丁）",
      os.path.isfile(rpath) and open(rpath, encoding="utf-8").read() == md, "")
    T("S17c 渲染器自带 R1 front matter（ASCII 两行）",
      "source_ir_version:" in md and "source_ir_fingerprint:" in md, md[:200])
    T("S18 报告 URL 指向静态 .md",
      isinstance(pub.get("url"), str) and pub["url"].endswith(".md")
      and "/reports/" in pub["url"], str(pub.get("url")))
    T("S19 报告文件落盘且含六区块", os.path.isfile(rpath)
      and all(t in open(rpath, encoding="utf-8").read() for t in
              ("## 结论", "## 命中的问题", "## 覆盖证明",
               "## 依据清单", "## 未审说明", "## 执行回执")), rpath)
    read_ok = store.read(pub["report_id"],
                         {"id": "u1", "role": "submitter", "tenant": "t1", "product_line": "p1"})
    T("S20 有权限可回读 URL", read_ok.get("ok") is True and read_ok.get("url") == pub["url"], str(read_ok))
    read_denied = store.read(pub["report_id"],
                             {"id": "u9", "role": "submitter", "tenant": "t1", "product_line": "p1"})
    T("S21 无权限不返回 URL", read_denied.get("ok") is False and read_denied.get("url") is None, str(read_denied))

    # ── 群消息 + send_gateway ─────────────────────────────────────
    msg_snapshot = dict(base_snapshot, report_url=pub["url"])
    msg = render("message", msg_snapshot)
    T("S22 report_render 生成群消息", msg.get("ok") is True, str(msg.get("errors"))[:300])
    text = msg.get("text") or ""
    T("S23 群消息一句且带报告链接",
      "\n" not in text and pub["url"] in text, str(text))
    mode = SG.decide_mode(text, has_eligible_card=False)
    T("S24 send_gateway 形态决策=text", mode.get("mode") == "text", str(mode.get("mode")))

    # ── 反向对照：decision 桩返回 PASS，但 coverage=partial ───────
    stub = {"state": "PASS", "layer": "DP1", "release_status": "待放行",
            "obligations": [], "run_state": "OK", "max_sev": "none",
            "max_sev_authority": "n/a", "any_authority_conflict": False,
            "all_evidence_gaps": [], "has_candidate": False, "chain": 15}
    stub_result = build(decision_override=stub).run(request)
    T("R1 桩确实返回 PASS", stub_result["decision"]["state"] == "PASS", str(stub_result["decision"]))
    T("R2 覆盖率仍是 partial", stub_result["coverage"].get("coverage_state") == "partial", "")
    errs = consistency_errors(stub_result)
    T("R3 partial+PASS 被一致性守卫拒绝（报告不得产出 PASS）",
      "partial_never_pass" in errs, str(errs))
    stub_snapshot = dict(base_snapshot, ir=stub_result["ir"])
    stub_render = render("report", stub_snapshot)
    stub_msg = render("message", stub_snapshot)
    T("R4 渲染器拒绝 PASS+partial 非法 IR（报告）",
      stub_render.get("ok") is False and stub_render.get("blocked") is True
      and any("L1-6" in str(e) for e in (stub_render.get("errors") or [])),
      str(stub_render.get("errors"))[:300])
    T("R4b 渲染器拒绝 PASS+partial 非法 IR（群消息）",
      stub_msg.get("ok") is False and stub_msg.get("blocked") is True,
      str(stub_msg.get("errors"))[:300])
    # 若一致性守卫放行，这里才会真正 publish；渲染器拒绝本身已使发布不可用。
    if not errs:
        stub_md = stub_render.get("markdown") or ""
        stub_pub = store.publish(stub_result["ir"], lambda _ir: stub_md,
                                 {"tenant": "t1", "product_line": "p1",
                                  "submitter_id": "u1", "assigned": []})
    else:
        stub_pub = {"ok": False, "url": None, "detail": "consistency_guard"}
    T("R5 桩报告未被发布（不会出现 PASS 报告）",
      stub_pub.get("ok") is False and stub_pub.get("url") is None, str(stub_pub))

    for f in FAILS:
        print("  ❌ " + f)
    verdict = "❌" if FAILS else "✅"
    print("\n%s smoke_end_to_end %d 项检查 · %d 项红" % (verdict, CHECKS, len(FAILS)))
    print("临时产物：")
    print("  数据根：%s" % store.root)
    print("  报告：%s" % pub.get("url"))
    print("  报告文件：%s" % rpath)
    print("  IR id：%s · receipt_id：%s" % (ir["ir_id"], receipt["receipt_id"]))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
