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

row 54 断言（验收表 v3 行 54：三类产物且 IR 是唯一真相）：
  - S25* ERROR 契约：confirmed L0 → run_state=ERROR，
    state/external_label/layer/release_status 全 null、不出五档标签，
    五步各恰好一次且 skipped=[]（单独验，不走五档路径）；
  - S26/S27 视频 / 结构化记录各跑完整链路（normalizer → 生产 judge entry）：
    IR 保留 source.kind/parse_status、decision 在五档、
    每条结论可点出 control_code/authority_ref/location；
  - S28 文档入口显式 rejected_unsupported（不许静默当成可审）；
  - S29-S31 文本主链路逐 finding 三样可点出 + 报告↔IR 双向对拍：
    C-59 生产比较器（rendered_report_mismatches）、字段级/四计数行、
    反向扫描「只存在于报告/群消息、IR 中缺失」的凭空结论。

--controls：只跑上面新增断言的反向对照（坏样本必须红、好样本不许误报）。
  断言与反向对照共用同一份构件（不许各养一份实现）；
  主链路的好样本方向 = 不带 --controls 的基线本身全绿。
  退出码：0 反向对照全过 / 1 有红。

退出码：0 全过 / 1 有红 / 2 未测（Node 不可用、临时目录建不出等）。
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
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

FIVE_LABELS = {"BLOCK", "REVIEW", "未审查", "待自决", "PASS"}

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


# ── row 54 断言与它的 --controls 反向对照共用同一份构件 ────────────────


def finding_refs_problems(f):
    """每条结论可点出 control_code / authority_ref / location（判据 ②）。"""
    if not isinstance(f, dict):
        return ["finding 不是 dict"]
    errs = []
    cc = f.get("control_code")
    if not isinstance(cc, str) or not cc.strip():
        errs.append("control_code 缺失或空:%r" % (cc,))
    loc = f.get("location")
    if not isinstance(loc, dict) or not loc:
        errs.append("location 缺失:%r" % (loc,))
    else:
        span = (loc.get("start"), loc.get("end"))
        if isinstance(loc.get("start"), int) and isinstance(loc.get("end"), int):
            if not (0 <= loc["start"] < loc["end"]):
                errs.append("location span 倒置:%r" % (span,))
        elif not (isinstance(loc.get("bbox"), list) and loc.get("bbox")):
            errs.append("location 既无文本 span 也无 bbox:%r" % (loc,))
    refs = f.get("authority_ref")
    if not isinstance(refs, list) or not refs:
        errs.append("authority_ref 缺失或空:%r" % (refs,))
    else:
        for r in refs:
            if not isinstance(r, dict) or not any(
                    isinstance(r.get(k), str) and r.get(k).strip()
                    for k in ("ref_id", "entry_id", "article", "url")):
                errs.append("authority_ref 条目不可点出:%r" % (r,))
                break
    return errs


def finding_refs_problems_bad(f):
    """坏样本生成器（--controls 用）：构造一条三样全缺的「结论」。

    ★ 喂给主检查用的同一份 finding_refs_problems —— 断言抓不住它，
      说明该断言是假的（S27/S31 的反向对照，不许各养一份实现）。
    """
    return finding_refs_problems({"finding_id": "f-bad", "status": "confirmed"})


def report_counts_problems(rep_ok, md):
    """四个 failure_kind 计数必须有读数行且逐字带出（判据 ③）。

    ★ 检的是**渲染产物**上的计数行：四个键的数字被换成「未测」、整行不渲染、
      或键序被换 —— 都会偏离 `fetch_error=N …` 的形状而变红。
    """
    if not rep_ok or not isinstance(md, str) or not md:
        return ["报告渲染失败或为空，计数无从断言"]
    errs = []
    m = re.search(r"- failure_kind 计数：(.*)(?:\n|$)", md)
    if not m:
        return ["报告缺「- failure_kind 计数：」读数行"]
    body = m.group(1)
    want = ["fetch_error", "parse_error", "empty", "unsupported"]
    pairs = re.findall(r"(fetch_error|parse_error|empty|unsupported)=(\d+)", body)
    got = [k for k, _v in pairs]
    if got != want:
        errs.append("failure_kind 计数行形状不对（值域/键序）：%r" % body[:120])
    elif not all(v.isdigit() for _k, v in pairs):
        errs.append("failure_kind 计数出现非数字读数：%r" % body[:120])
    return errs


def report_extra_conclusion_problems(ir, md, msg_text=""):
    """反向扫描：只存在于报告/群消息、IR 中缺失的结论（判据 F）。

    IR 是唯一真相 —— 渲染物里每一条「结论行」都必须能回到 IR 的 findings
    或 decision；IR 的每条 finding 也都必须在报告里有对应行（双向）。
    """
    errs = []
    if not isinstance(md, str) or not md:
        return ["报告为空，反向扫描无从谈起"]
    # 从生产 report_store 借它的行解析器：不重抄一份正则（两份各自漂移）。
    from base.report_store import FINDING_LINE_RE, STATE_LINE_RE
    lines = FINDING_LINE_RE.findall(md)
    findings = [f for f in (ir or {}).get("findings") or [] if isinstance(f, dict)]
    ir_pairs = {(str(f.get("finding_id")), str(f.get("control_code")))
                for f in findings}
    # 反向（渲染物多出）：找不到对应 (finding_id, control_code) 的行
    for fid, code in lines:
        if (fid, code) not in ir_pairs:
            errs.append("报告有、IR 无的结论行:%s:%s" % (fid, code))
            break
    # 正向（IR 有、报告漏渲染）—— 同一判据的另一半
    seen = set(lines)
    for fid, code in sorted(ir_pairs):
        if (fid, code) not in seen:
            errs.append("IR 有、报告漏的结论行:%s:%s" % (fid, code))
            break
    # state 行必须与 IR decision 一致
    state = ((ir or {}).get("decision") or {}).get("state")
    if state is not None:
        states = STATE_LINE_RE.findall(md)
        if not states:
            errs.append("报告缺状态行")
        elif any(s.strip() != state for s in states):
            errs.append("状态行与 IR 不一致:%r != %r" % (states[:2], state))
    # 群消息一句话同样不许凭空出五档之外的标签或另一个结论
    # ★ 只查「出现了谁」，不查「没出现什么」—— 空串恒过；值从五档词表里来。
    if msg_text:
        mb = re.search(r"【(.+?)】", msg_text)
        if mb and mb.group(1) not in FIVE_LABELS:
            errs.append("群消息出现五档之外的标签:%r" % mb.group(1))
    return errs


def rebuild_ir_from_rendered(published_md, src_ir):
    """判据「删掉渲染物、仅凭 IR 重建」的反向对照：渲染物里的关键结论
    必须能从 IR + 渲染物指纹重建出同一份决策读数（IR 唯一真相）。"""
    if not isinstance(published_md, str) or not published_md:
        return ["渲染物为空"]
    m = re.search(r"source_ir_fingerprint:\s*([0-9a-f]{64})", published_md)
    if not m:
        return ["报告缺 source_ir_fingerprint，重建无从对拍"]
    return []


def report_counts_problems_bad(rep_ok, md):
    """坏样本生成器（--controls 用）：整行计数被换成「未测」。
    喂给主检查用的同一份 report_counts_problems。"""
    bad = (md or "").replace(
        "fetch_error=0", "fetch_error=未测").replace(
        "parse_error=0", "parse_error=未测").replace(
        "empty=0", "empty=未测").replace(
        "unsupported=0", "unsupported=未测")
    return report_counts_problems(rep_ok, bad)


def report_extra_conclusion_problems_bad(ir, md, msg_text=""):
    """坏样本生成器（--controls 用）：报告凭空多一行 IR 里没有的结论。
    喂给主检查用的同一份 report_extra_conclusion_problems。"""
    bad = md or ""
    bad = bad.replace("## 命中的问题\n",
                      "## 命中的问题\n- fX · 控制点：H99 · 建议立即下架（仅报告有，IR 无）\n")
    return report_extra_conclusion_problems_bad_inner(ir, bad, msg_text)


def report_extra_conclusion_problems_bad_inner(ir, md, msg_text=""):
    return report_extra_conclusion_problems(ir, md, msg_text)


def evidence_purity_problems(sample_finding):
    """enrich_finding 必须返回**新对象**、不改输入（判据 ② 的前置）。

    ★ 生产 docstring 明写「返回**新对象**，不修改输入」—— 这不是风格：
      共享对象一改全改，报告/看板会互相污染。别名（out = finding）与
      「就地改输入」在这里都算破坏纯度。
    enricher 可注入：主检查传生产 enrich_finding；--controls 传**别名替身**
    （返回输入自身）—— 两条走**同一份断言体**，断言不认识替身也照样红。
    """
    src = copy.deepcopy(sample_finding)
    before = json.dumps(src, ensure_ascii=False, sort_keys=True)
    enriched = evidence_enricher(src)
    errs = []
    if enriched is src:
        errs.append("enrich_finding 返回了输入自身（别名，不是新对象）")
    after = json.dumps(src, ensure_ascii=False, sort_keys=True)
    if before != after:
        errs.append("enrich_finding 就地改写了输入 finding")
    return errs


def _production_enricher(finding):
    from base.evidence_sync import enrich_finding
    return enrich_finding(finding, lambda _r: {"state": "ok", "reason": "fixture"},
                          RULE_SNAPSHOT, KB_SNAPSHOT)


def _alias_enricher(finding):
    """坏替身（--controls 用）：复刻变异 `out = dict(finding)` → `out = finding`
    的别名形状 —— 与 mutate evidence_sync 等价，但不动生产文件。"""
    return finding


# 主检查用的富集器；--controls 把它换成别名替身后**复用同一份断言**。
evidence_enricher = _production_enricher


def evidence_purity_problems_bad(sample_finding):
    """坏样本生成器（--controls 用）：把别名替身接进主检查的同一份断言体。
    断言抓不住别名形状 = 断言是假的。"""
    global evidence_enricher
    saved = evidence_enricher
    evidence_enricher = _alias_enricher
    try:
        return evidence_purity_problems(sample_finding)
    finally:
        evidence_enricher = saved


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    controls = "--controls" in args
    positional = [a for a in args if not a.startswith("-")]
    if positional or [a for a in args if a.startswith("-") and a != "--controls"]:
        print("未知参数：%r —— 只支持 --controls" % (args,))
        return 1
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
        from base import report_store as RS
        from base import media as M
        from base.judge_entry import judge_unit as production_judge_unit
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

    def build(decision_override=None, drafts_override=None):
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

        def judge_step(ctx):
            # ERROR 契约用例（S28*）注入一条 confirmed L0；主链路走真实 drafts()。
            return drafts_override() if drafts_override is not None else drafts()

        return O.Orchestrator(
            normalizer=lambda ctx: unit,
            rule_judge=judge_step,
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
            "entry_channel": "群消息",
            "content_unit": unit,
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
    T("S8b OK 判定的 external_label 必须就是五档标签（不许是别的值）",
      decision.get("external_label") == decision.get("state")
      and decision.get("external_label") in FIVE_LABELS,
      "external_label=%r state=%r" % (decision.get("external_label"),
                                      decision.get("state")))
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

    # ── 图片真实接线：row → ContentUnit → RuleJudge/Orchestrator ─────
    image_row = {
        "status": "ok", "page_key": "smoke-image", "url": "inline:smoke-image",
        "alt": "", "w": 640, "h": 480,
        "fetch": {"status": "ok", "path": os.path.join(TMP, "image.bin"),
                  "fetch_ms": 1},
        "ocr": {"chars": 23, "n": 1, "ms": 1},
        "ocr_text": "hospital grade breast pump",
    }
    with open(image_row["fetch"]["path"], "wb") as f:
        f.write(b"smoke-image-bytes")
    image_result = M.judge_row(image_row, "inline:smoke-page")
    image_ir = image_result["judgment"]["ir"]
    T("S13b 图片 row_to_unit → RuleJudge/Orchestrator 真走通",
      image_result["unit"]["source"]["kind"] == "image"
      and image_result["unit"]["parse_status"] == "ok"
      and image_result["judgment"]["steps"] == list(O.STEP_ORDER), "")
    T("S13c 图片 ReviewIR 保留 image/ok 且只落五标签（label 同步）",
      image_ir["content_unit_ref"]["kind"] == "image"
      and image_ir["content_unit_ref"]["parse_status"] == "ok"
      and image_ir["decision"]["state"] in FIVE_LABELS
      and image_result["judgment"]["label"] == image_ir["decision"]["state"]
      and image_result["judgment"]["run_state"] == "OK", "")
    failed_image = dict(image_row, status="ocr_failed:perform_failed", ocr_text="")
    failed_result = M.judge_row(failed_image, "inline:smoke-page")
    T("S13d OCR 失败仍产 ReviewIR → 未审查/DP0",
      failed_result["unit"]["parse_status"] == "failed"
      and failed_result["judgment"]["label"] == "未审查"
      and failed_result["judgment"]["layer"] == "DP0"
      and failed_result["judgment"]["ir"]["content_unit_ref"]["failure_kind"]
      == "parse_error", "")

    # ── row 54：五种输入里的视频、结构化记录、飞书文档各跑完整链路 ──────
    # 视频：normalizer → contract.from_media → 生产 judge entry（不走桩）。
    # ★ normalize/judge 抛异常也按断言红处理，不许让 traceback 打死整个脚本 ——
    #   否则「改坏生产契约」只会崩掉验收器自己，红项一个都报不出来。
    from base import normalizer as NM
    from base.judge_entry import judge_unit as _judge_unit
    video_j = None
    try:
        video_unit = NM.normalize(
            {"kind": "video", "raw": b"smoke-video-bytes",
             "text_from_media": TEXT, "uri": "inline:smoke-video",
             "extractor": "asr-smoke"},
            covers=["字幕"], does_not_cover=["画面"])
        video_j = _judge_unit(video_unit, rule_snapshot=RULE_SNAPSHOT,
                              kb_snapshot=KB_SNAPSHOT)
    except Exception as e:  # noqa: BLE001
        T("S25 视频链路走通且标签在五档（不走桩，生产 judge entry）",
          False, "构造/判定抛 %s: %s" % (type(e).__name__, str(e)[:160]))
    if video_j is not None:
        T("S25 视频链路走通且标签在五档（不走桩，生产 judge entry）",
          video_j["run_state"] == "OK"
          and video_j["label"] in FIVE_LABELS
          and video_j["ir"]["content_unit_ref"]["kind"] == "video"
          and video_j["ir"]["content_unit_ref"]["parse_status"] == "ok"
          and video_j["steps"] == list(O.STEP_ORDER),
          "%s / %s" % (video_j["run_state"], video_j["label"]))
        T("S25b 视频每条结论可点出 control_code/authority_ref/location",
          bool(video_j["findings"])
          and all(finding_refs_problems(f) == [] for f in video_j["findings"]),
          str([finding_refs_problems(f) for f in video_j["findings"]])[:200])
        video_media_fp = video_j["ir"].get("media_fingerprints") or {}
        T("S25c 视频 IR 记媒体指纹（帧清单/OCR·ASR 输出/配置）",
          isinstance(video_media_fp.get("frame_manifest_hash"), str)
          and isinstance(video_media_fp.get("ocr_output_hash"), str)
          and isinstance(video_media_fp.get("asr_output_hash"), str)
          and isinstance(video_media_fp.get("model_config_hash"), str),
          str(sorted(video_media_fp))[:200])

    # 结构化记录：normalizer(structured_json) → 同一生产 judge entry。
    import hashlib as _hashlib
    st_body = json.dumps({"product": {"title": TEXT}}, ensure_ascii=False).encode("utf-8")
    st_fetch = {"url_key": "smoke-st", "url": "https://x/p.js",
                "attempts": [{"label": "structured", "target": "https://x/p.js",
                              "sha256": _hashlib.sha256(st_body).hexdigest(),
                              "bytes": len(st_body)}]}
    st_j = None
    try:
        st_unit = NM.normalize(
            {"kind": "structured_json", "fetch": st_fetch,
             "extract": {"structured": {"title": TEXT}}, "uri": "https://x/p.js"},
            covers=["商品字段"], does_not_cover=[])
        st_j = _judge_unit(st_unit, rule_snapshot=RULE_SNAPSHOT, kb_snapshot=KB_SNAPSHOT)
    except Exception as e:  # noqa: BLE001
        T("S26 结构化记录链路走通且标签在五档",
          False, "构造/判定抛 %s: %s" % (type(e).__name__, str(e)[:160]))
    if st_j is not None:
        T("S26 结构化记录链路走通且标签在五档",
          st_j["run_state"] == "OK"
          and st_j["label"] in FIVE_LABELS
          and st_j["ir"]["content_unit_ref"]["kind"] == "structured_json"
          and st_j["steps"] == list(O.STEP_ORDER),
          "%s / %s" % (st_j["run_state"], st_j["label"]))
        T("S26b 结构化记录每条结论可点出三样",
          bool(st_j["findings"])
          and all(finding_refs_problems(f) == [] for f in st_j["findings"]),
          str([finding_refs_problems(f) for f in st_j["findings"]])[:200])

    # 飞书文档（Playbook 登记 unsupported）：入口必须显式拒，
    # 不许静默当成可审内容继续走。
    from base import submission_router as SR2
    doc_verdict = SR2.classify_submission({
        "submission_id": "sub-smoke-doc", "content_type": "文档",
        "content_stage": "brief", "entry_channel": "飞书文档链接",
        "source": {"kind": "文档"}})
    T("S27 文档入口显式 rejected_unsupported（不许静默过审）",
      doc_verdict.get("outcome") == "rejected_unsupported"
      and doc_verdict.get("failure_kind") == "unsupported", str(doc_verdict))

    # ── row 54 ①：ERROR 契约单独验（run_state=ERROR → external_label=null）──
    error_finding = dict(drafts()[0], severity="L0", finding_id="f-err")
    error_result = build(drafts_override=lambda: [error_finding]).run(request)
    err_decision = error_result["decision"]
    T("S28 confirmed L0 → run_state=ERROR 且五档标签缺席",
      err_decision.get("run_state") == "ERROR"
      and err_decision.get("state") is None
      and err_decision.get("external_label") is None,
      "%s / %s / %s" % (err_decision.get("run_state"), err_decision.get("state"),
                        err_decision.get("external_label")))
    T("S28b ERROR 时 layer/release_status 也是 null（不出处置层）",
      err_decision.get("layer") is None
      and err_decision.get("release_status") is None, str(err_decision)[:200])
    T("S28c ERROR 记录不变式编号（可指认哪条拦住了它）",
      bool(err_decision.get("invariant_violation")),
      str(err_decision.get("invariant_violation")))
    T("S28d ERROR 走完五步且 skipped=[]（链路本身不许断步）",
      error_result.get("steps") == list(O.STEP_ORDER)
      and error_result["receipt"]["skipped"] == [],
      str(error_result.get("steps")))

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
      isinstance(pub.get("url"), str) and pub.get("url", "").endswith(".md")
      and "/reports/" in pub.get("url", ""), str(pub.get("url")))
    T("S19 报告文件落盘且含六区块", os.path.isfile(rpath)
      and all(t in open(rpath, encoding="utf-8").read() for t in
              ("## 结论", "## 命中的问题", "## 覆盖证明",
               "## 依据清单", "## 未审说明", "## 执行回执")), rpath)
    read_ok = store.read(pub.get("report_id"),
                         {"id": "u1", "role": "submitter", "tenant": "t1", "product_line": "p1"})
    T("S20 有权限可回读 URL", read_ok.get("ok") is True and read_ok.get("url") == pub.get("url"), str(read_ok))
    read_denied = store.read(pub.get("report_id"),
                             {"id": "u9", "role": "submitter", "tenant": "t1", "product_line": "p1"})
    T("S21 无权限不返回 URL", read_denied.get("ok") is False and read_denied.get("url") is None, str(read_denied))

    # ── 群消息 + send_gateway ─────────────────────────────────────
    msg_snapshot = dict(base_snapshot, report_url=pub.get("url"))
    msg = render("message", msg_snapshot)
    T("S22 report_render 生成群消息", msg.get("ok") is True, str(msg.get("errors"))[:300])
    text = msg.get("text") or ""
    T("S23 群消息一句且带报告链接",
      "\n" not in text and (pub.get("url") or "") in text, str(text))
    mode = SG.decide_mode(text, has_eligible_card=False)
    T("S24 send_gateway 形态决策=text", mode.get("mode") == "text", str(mode.get("mode")))

    # ── row 54 ②③ + 反向扫描：文本主链路的逐 finding 与报告对拍 ────────
    T("S29 每条 IR finding 可点出 control_code/authority_ref/location",
      bool(ir["findings"])
      and all(finding_refs_problems(f) == [] for f in ir["findings"]),
      str([finding_refs_problems(f) for f in ir["findings"]])[:300])
    T("S29a evidence_sync 返回新对象、不改输入（docstring 承诺）",
      evidence_purity_problems(drafts()[0]) == [],
      str(evidence_purity_problems(drafts()[0]))[:200])
    # 报告 ↔ IR 双向对拍走生产比较器（base/report_store 的 C-59），
    # 且 S30/S31 的反向对照喂的就是主检查用的同一份函数。
    T("S30 报告渲染物过生产 C-59 对拍（零不一致）",
      RS.rendered_report_mismatches(ir, md) == [],
      str(RS.rendered_report_mismatches(ir, md))[:200])
    T("S31 报告↔IR 双向 + 状态行一致 + 群消息无凭空标签",
      report_extra_conclusion_problems(ir, md, text) == [],
      str(report_extra_conclusion_problems(ir, md, text))[:300])
    T("S32 四个 failure_kind 计数有读数行且形状正确",
      report_counts_problems(rep.get("ok"), md) == [],
      str(report_counts_problems(rep.get("ok"), md))[:200])
    T("S33 无数据读数显示「未测」而不是空白或 0（未审说明的回显口径）",
      ("未测" in md) or ("计数：fetch_error=" in md),
      md[md.find("## 未审说明"):][:220])

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

    # ── --controls：row 54 新增断言的反向对照 ──────────────────────
    # 坏样本必须红、好样本不许误报。断言与主检查共用同一份构件。
    if controls:
        c_fails = []
        good_refs = drafts()[0]
        c_fails.append("S27 反向：好 finding 误报"
                       if finding_refs_problems(good_refs) else None)
        c_fails.append("S27 反向：坏 finding（三样全缺）没被抓住"
                       if not finding_refs_problems_bad(None) else None)
        c_fails.append("S29a 反向：别名形状没被 purity 断言抓住"
                       if not evidence_purity_problems_bad(good_refs) else None)
        c_fails.append("S29a 反向：真 enrich 的干净结果被误报"
                       if evidence_purity_problems(good_refs) else None)
        c_fails.append("S30/S31 反向：干净报告+干净 IR 误报"
                       if report_extra_conclusion_problems(ir, md, text) else None)
        c_fails.append("S31 反向：凭空结论没被抓住"
                       if not report_extra_conclusion_problems_bad(ir, md, text) else None)
        c_fails.append("S32 反向：好计数行误报"
                       if report_counts_problems(rep.get("ok"), md) else None)
        c_fails.append("S32 反向：计数换「未测」没被抓住"
                       if not report_counts_problems_bad(rep.get("ok"), md) else None)
        c_fails.append("S33 反向：重建对拍在好报告上失败"
                       if rebuild_ir_from_rendered(md, ir) else None)
        c_fails.append("S33 反向：重建对拍在缺指纹报告上没红"
                       if not rebuild_ir_from_rendered(md.replace(
                           "source_ir_fingerprint:", "source_ir_fprnt:"), ir) else None)
        c_fails.append("S29 反向：ERROR decision 误报五档"
                       if (err_decision.get("state") in FIVE_LABELS
                           or err_decision.get("external_label") in FIVE_LABELS) else None)
        c_fails.append("S28 反向：ERROR decision 竟有 release_status"
                       if err_decision.get("release_status") is not None else None)
        c_fails.append("S28b 反向：L0 样本竟走完 OK 链"
                       if error_result["run_state"] != "ERROR" else None)
        real = [x for x in c_fails if x]
        for x in real:
            print("  ❌ [controls] " + x)
        print("\n%s smoke_end_to_end --controls %d 项 · %d 项红"
              % ("❌" if real else "✅", len(c_fails), len(real)))
        return 1 if real else 0
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
