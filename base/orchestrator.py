#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/orchestrator.py — T1-15：唯一编排器（五步串联 + ReviewIR + 回执）

五步固定顺序、每步恰好一次、无回边、无提前停、无轮次：
    normalize → judge → dispose → output → evaluate

边界：
- 每个部件可注入；默认接已交付模块（normalizer / coverage_composer /
  decision_table / disposition_router，其余按需注入）。
- parse_status=failed：**judge 部件一次都不调用**，findings=[]，不产 judge 标签；
  五步仍然全部跑完（无提前停），控制点记为未跑。
- 只组装 ReviewIR 与 receipt；不写盘、不发送、不落 finding 存储。
- receipt 的 `skipped` 恒为 `[]`，且必须出现（空数组不省略）。
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

STEP_ORDER = ("normalize", "judge", "dispose", "output", "evaluate")


def _workflow_timing(receipt):
    """算工作流耗时读数。**实现只在 `base/workflow_timing.py` 一处**。

    ★ 这里刻意**不**复制算法：报告与接口都要读这个数，
      算法放两处就是两套口径，迟早各自漂移（AGENTS.md §2.4.8）。
    ★ import 失败时落 untested 而不是抛 —— 一张报告不该因为一个读数没算出来就整份失败；
      但 `status` 会变成 `untested`，报告里写「未测」，不会冒充 0。
    """
    try:
        from base import workflow_timing as _wt
        return _wt.compute(receipt)
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "untested",
            "reason": "workflow_timing 不可用：%s" % (type(exc).__name__,),
            "total_ms": None,
            "step_count": 0,
            "slowest": [],
            "source": "steps-duration-sum",
        }


REQUIRED_IR_FIELDS = (
    "ir_id", "ir_version", "content_unit_ref", "source_ir_version",
    "findings", "decision", "coverage", "receipt_ref",
    "rule_snapshot", "kb_snapshot", "control_points_version", "created_at",
)

REQUIRED_RECEIPT_FIELDS = (
    "receipt_id", "unit_id", "skill_id", "skill_version", "skill_hash",
    "started_at", "ended_at", "steps", "skipped",
    "rule_snapshot", "kb_snapshot",
    "obligations", "invariant_violation", "control_points_ran",
    "control_points_version", "video_sampling", "disposition",
)

#: 覆盖证明里「未跑的为什么」的已知集合。★ 2026-10-23 T-120b：加上
#: `no_control_points` —— 空族的原因是「这一族还没有控制点」，与 `not_wired`
#: （接线没做）是两件事。此前它不在这个元组里，于是走下面的**降级分支**，
#: 产品侧读到的是 not_wired，界面把它说成「没接线」。
VALID_REASON = ("no_capability", "no_rule", "not_wired", "no_control_points")
UNKNOWN_BUCKET_KEYS = ("family", "scene_domain", "authority_source", "consequence")
FAILURE_KIND_KEYS = ("fetch_error", "parse_error", "empty", "unsupported")


def _iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(ts)))


def _short_hash(*parts):
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:16]


def _as_findings(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        if value.get("status") == "untested":
            return []
        return list(value.get("findings") or [])
    return []


def _merge_does_not_cover(cov, unit):
    """`does_not_cover` 的两条来源合并：unit 的声明在前，coverage 自带的补在后面。

    ★ 2026-10-26 T-430：此前这个字段在 `_coverage_ir` 里被整块丢掉，而
      `contract.from_media()` 刻意不给它默认值（默认值会让「只做了 OCR」
      看起来像「图片已审」）。于是那份声明在最后一跳被静默取消 ——
      文本上无害（文本的该字段本来就空），**一开媒体就等于把没审的部分伪装成审过**。

    方向是**只许变多、不许变少**：coverage 想收窄 unit 的声明，在这里收窄不了。
    两个来源都查，是因为它们会各自单独出现：composer 的输出可能只带到自己那半，
    而 `unit.textification` 才是调用方逐字写下的那份原始声明。
    """
    out = []
    for src in ((unit or {}).get("textification") or {},
                cov if isinstance(cov, dict) else {}):
        for item in (src.get("does_not_cover") or []):
            if isinstance(item, str) and item.strip() and item not in out:
                out.append(item)
    return out


def _coverage_ir(value, request, unit):
    """把 composer 输出 / 直接 coverage 统一成 ReviewIR 的 coverage 形状。"""
    req_cps = list(request.get("control_points") or [])
    if isinstance(value, dict) and "coverage_state" in value \
            and "modalities_evaluated" in value:
        cov = dict(value)
    elif isinstance(value, dict) and isinstance(value.get("coverage"), dict):
        src = value["coverage"]
        cov = {
            "coverage_state": value.get("coverage_state") or src.get("coverage_state"),
            "modalities_evaluated": list(src.get("modalities_evaluated") or []),
            "rules_version": src.get("rules_version"),
            "control_points_applied": list(src.get("control_points_applied") or req_cps),
            "not_evaluated_reason": list(src.get("not_evaluated_reason")
                                          or src.get("not_run_reasons") or []),
            "does_not_cover": list(src.get("does_not_cover") or []),
        }
    else:
        cov = {"coverage_state": "missing", "modalities_evaluated": [],
               "rules_version": request.get("rule_snapshot"),
               "control_points_applied": req_cps,
               "not_evaluated_reason": [{"what": "coverage_composer",
                                          "why": "not_wired"}]}

    reasons = []
    for r in list(cov.get("not_evaluated_reason") or []):
        if not isinstance(r, dict):
            continue
        why = r.get("why")
        if why in VALID_REASON:
            entry = {"what": str(r.get("what") or "未说明"), "why": why}
            # ★ 2026-10-23 T-120b：label 是 why 的可读面（空族要求逐字「未做·无控制点」）。
            #   上层给了就原样带下去；**不要**在这里重新生成，否则同一原因会有两份措辞。
            label = r.get("label")
            if isinstance(label, str) and label.strip():
                entry["label"] = label
            reasons.append(entry)
        else:
            reasons.append({
                "what": "%s（%s）" % (r.get("what") or "未说明", why),
                "why": "not_wired",
            })
    cov["not_evaluated_reason"] = reasons
    cov["coverage_state"] = cov.get("coverage_state") or "missing"
    cov["modalities_evaluated"] = list(cov.get("modalities_evaluated") or [])
    cov["control_points_applied"] = list(cov.get("control_points_applied") or req_cps)
    # ★ T-430：两条路都要兜 —— 上面各分支负责「搬过来」，这里负责
    #   「coverage 里没有时从 unit.textification 补回来」。少任何一条，
    #   只走其中一条路的调用方就会被静默丢掉声明。
    cov["does_not_cover"] = _merge_does_not_cover(cov, unit)
    rv = cov.get("rules_version")
    if not isinstance(rv, str):
        rv = json.dumps(rv, ensure_ascii=False, sort_keys=True) if rv is not None else "unknown"
    cov["rules_version"] = rv
    return cov


def _decision_view(value):
    if not isinstance(value, dict):
        return {
            "run_state": "ERROR", "state": None, "layer": None,
            "release_status": None, "obligations": [],
            "invariant_violation": "DECISION", "error_reason": "decision not configured",
        }
    out = dict(value)
    out.setdefault("obligations", [])
    out.setdefault("run_state", "OK")
    return out


def _disposition_view(value, decision):
    if isinstance(value, dict):
        out = dict(value)
    else:
        out = {}
    out["state"] = out.get("state") or decision.get("state")
    out["layer"] = out.get("layer") or decision.get("layer")
    out["release_status"] = "待放行"
    return out


def validate_receipt(receipt):
    p = []
    if not isinstance(receipt, dict):
        return ["receipt 必须是 dict"]
    missing = [k for k in REQUIRED_RECEIPT_FIELDS if k not in receipt]
    if missing:
        p.append("缺少字段 %r" % (missing,))
    if receipt.get("skipped") != []:
        p.append("skipped 必须是 []（不许省略/不许写跳过）")
    steps = receipt.get("steps")
    if not isinstance(steps, list) or len(steps) != 5:
        p.append("steps 必须恰好 5 条")
    else:
        names = [s.get("name") for s in steps]
        if names != list(STEP_ORDER):
            p.append("steps 顺序必须是 %r，实际 %r" % (list(STEP_ORDER), names))
        for s in steps:
            if not {"name", "input_summary", "output_summary", "duration_ms"} <= set(s):
                p.append("step 字段不全：%r" % (s,))
    disp = receipt.get("disposition")
    if not isinstance(disp, dict) or not {"state", "layer", "release_status"} <= set(disp):
        p.append("disposition 必须含 state/layer/release_status")
    elif disp.get("release_status") != "待放行":
        p.append("disposition.release_status 必须固定为 待放行")
    iv = receipt.get("invariant_violation")
    if iv is not None and (not isinstance(iv, dict) or "code" not in iv):
        p.append("invariant_violation 必须是 null 或含 code 的对象")
    vs = receipt.get("video_sampling")
    if vs is not None and (not isinstance(vs, dict)
                           or not {"interval_ms", "total_frames"} <= set(vs)):
        p.append("video_sampling 必须是 null 或含 interval_ms/total_frames")
    return p


def validate_ir(ir):
    p = []
    if not isinstance(ir, dict):
        return ["ir 必须是 dict"]
    missing = [k for k in REQUIRED_IR_FIELDS if k not in ir]
    if missing:
        p.append("缺少字段 %r" % (missing,))
    ref = ir.get("content_unit_ref")
    if not isinstance(ref, dict) or not {"unit_id", "kind", "parse_status"} <= set(ref):
        p.append("content_unit_ref 必须含 unit_id/kind/parse_status")
    elif ref.get("parse_status") == "failed" and not ref.get("failure_kind"):
        p.append("content_unit_ref failed 必须含 failure_kind")
    dec = ir.get("decision")
    if not isinstance(dec, dict) or not {"state", "layer", "release_status"} <= set(dec):
        p.append("decision 必须含 state/layer/release_status")
    cov = ir.get("coverage")
    if not isinstance(cov, dict) or not {
            "coverage_state", "modalities_evaluated",
            "rules_version", "control_points_applied"} <= set(cov):
        p.append("coverage 缺四项证明")
    return p


class Orchestrator(object):
    def __init__(self, *, submission=None, normalizer=None, rule_judge=None,
                 semantic_judge=None, evidence=None, coverage=None,
                 decision=None, disposition=None, renderer=None, store=None,
                 gateway=None, evaluator=None, control_points_version=None,
                 clock=None):
        self.submission = submission
        self.normalizer = normalizer
        self.rule_judge = rule_judge
        self.semantic_judge = semantic_judge
        self.evidence = evidence
        self.coverage = coverage
        self.decision = decision
        self.disposition = disposition
        self.renderer = renderer
        self.store = store
        self.gateway = gateway
        self.evaluator = evaluator
        self.control_points_version = control_points_version
        self.clock = clock or time.time

    def _call(self, component, ctx):
        if component is None:
            return None
        if callable(component):
            return component(ctx)
        return component

    def _cp_version(self, request):
        version = (request.get("control_points_version")
                   or self.control_points_version)
        if version:
            return version
        try:
            from base.control_points import ControlPointRegistry
            return ControlPointRegistry().table_version
        except Exception:  # noqa: BLE001
            return "unknown"

    def _default_normalize(self, ctx):
        from base import normalizer as N
        req = ctx["request"]
        raw = req.get("raw_input")
        if raw is None:
            raw = {"kind": "free_text", "text": req.get("text") or "",
                   "uri": "inline:orchestrator"}
        return N.normalize(
            raw,
            covers=req.get("covers"),
            does_not_cover=req.get("does_not_cover"),
            parse_status=req.get("parse_status", "ok"),
            failure_kind=req.get("failure_kind"),
            reason=req.get("reason"),
        )

    def _default_coverage(self, ctx):
        try:
            from base import coverage_composer as CC
            req = ctx["request"]
            unit = ctx["unit"]
            modalities = req.get("modalities_evaluated") or [
                (unit.get("source") or {}).get("kind") or "unknown"]
            cps = list(req.get("control_points") or [])
            by_family = req.get("control_points_by_family") or {
                cp: "ran" for cp in cps}
            out = CC.compose_and_derive(
                modalities_evaluated=modalities,
                rules_version=req.get("rules_version") or req.get("rule_snapshot") or "unknown",
                control_points_by_family=by_family,
                not_run_reasons=req.get("not_run_reasons") or [],
                does_not_cover=req.get("does_not_cover") or [],
                empty_families=req.get("empty_families"),
                parse_status=unit.get("parse_status", "ok"),
            )
            return _coverage_ir(out, req, unit)
        except Exception:  # noqa: BLE001
            return _coverage_ir(None, ctx["request"], ctx["unit"])

    def _default_decision(self, ctx):
        from base.decision_table import decide
        unit = ctx["unit"]
        cov = ctx["coverage"]
        return decide({
            "parse_status": unit.get("parse_status", "ok"),
            "failure_kind": unit.get("failure_kind"),
            "coverage_state": cov.get("coverage_state", "missing"),
            "findings": ctx["findings"],
        })

    def _default_disposition(self, ctx):
        from base.disposition_router import DispositionRouter
        return DispositionRouter().route(
            ctx["decision"], ctx["receipt_id"])

    def run(self, request, *, unit=None):
        if not isinstance(request, dict):
            raise ValueError("request 必须是 dict")
        ctx = {"request": dict(request), "unit": unit or request.get("unit")}
        steps = []
        run_state = "OK"
        started = self.clock()

        def step(name, fn, summarize):
            nonlocal run_state
            t0 = self.clock()
            try:
                out = fn()
                status = "ok"
            except Exception as exc:  # noqa: BLE001
                run_state = "ERROR"
                out = {"error": "%s: %s" % (type(exc).__name__, exc)}
                status = "error"
            t1 = self.clock()
            entry = {
                "name": name,
                "input_summary": summarize("input", ctx),
                "output_summary": summarize("output", out) if status == "ok"
                else str(out["error"]),
                "duration_ms": round((t1 - t0) * 1000, 3),
            }
            steps.append(entry)
            return out

        receipt_id = "rc-" + _short_hash(
            "receipt-v1", ctx["request"].get("skill_id"),
            ctx["request"].get("skill_hash"), started)

        def do_normalize():
            if self.submission is not None:
                sub = self._call(self.submission, ctx)
                if sub is not None:
                    ctx["submission"] = sub
            if ctx["unit"] is None:
                if self.normalizer is not None:
                    ctx["unit"] = self._call(self.normalizer, ctx)
                else:
                    ctx["unit"] = self._default_normalize(ctx)
            if not isinstance(ctx["unit"], dict):
                raise ValueError("normalizer 必须返回 ContentUnit")
            return {"unit_id": ctx["unit"].get("unit_id"),
                    "parse_status": ctx["unit"].get("parse_status", "ok")}

        def do_judge():
            u = ctx["unit"]
            failed = u.get("parse_status") == "failed"
            ctx["judge_invoked"] = not failed
            if failed:
                ctx["findings"] = []
                return {"gate": "parse_status=failed", "findings": 0}
            rule = self._call(self.rule_judge, ctx) if self.rule_judge is not None else []
            sem = self._call(self.semantic_judge, ctx) if self.semantic_judge is not None else {
                "status": "untested", "findings": []}
            ctx["findings"] = _as_findings(rule) + _as_findings(sem)
            return {"findings": len(ctx["findings"])}

        def do_dispose():
            ctx["evidence"] = self._call(self.evidence, ctx) if self.evidence is not None else ctx["findings"]
            ctx["findings"] = _as_findings(ctx["evidence"])
            cov_raw = (self._call(self.coverage, ctx) if self.coverage is not None
                       else self._default_coverage(ctx))
            ctx["coverage"] = _coverage_ir(cov_raw, ctx["request"], ctx["unit"])
            dec_raw = (self._call(self.decision, ctx) if self.decision is not None
                       else self._default_decision(ctx))
            ctx["decision"] = _decision_view(dec_raw)
            if ctx["unit"].get("parse_status") == "failed":
                ctx["decision"].update({
                    "state": "未审查", "layer": "DP0",
                    "release_status": "待放行",
                    "obligations": list(ctx["decision"].get("obligations") or []),
                })
            ctx["receipt_id"] = receipt_id
            disp_raw = (self._call(self.disposition, ctx)
                        if self.disposition is not None
                        else self._default_disposition(ctx))
            ctx["disposition"] = _disposition_view(disp_raw, ctx["decision"])
            if ctx["unit"].get("parse_status") == "failed":
                ctx["disposition"]["state"] = "未审查"
                ctx["disposition"]["layer"] = "DP0"
            return {"state": ctx["decision"].get("state"),
                    "layer": ctx["decision"].get("layer"),
                    "findings": len(ctx["findings"])}

        def do_output():
            ctx["render"] = self._call(self.renderer, ctx) if self.renderer is not None else None
            ctx["stored"] = self._call(self.store, ctx) if self.store is not None else None
            ctx["sent"] = self._call(self.gateway, ctx) if self.gateway is not None else None
            return {"rendered": ctx["render"] is not None,
                    "stored": ctx["stored"] is not None,
                    "sent": ctx["sent"] is not None}

        def do_evaluate():
            ctx["evaluation"] = (self._call(self.evaluator, ctx)
                                 if self.evaluator is not None else None)
            return {"evaluated": ctx["evaluation"] is not None}

        def summ(phase, value):
            if phase == "input":
                if isinstance(value, dict) and value.get("unit_id"):
                    return "unit=%s" % value.get("unit_id")
                if isinstance(value, dict) and value.get("request"):
                    return "request"
                return "input"
            if isinstance(value, dict):
                return json.dumps(value, ensure_ascii=False, sort_keys=True)[:160]
            return str(value)[:160]

        # 固定顺序、恰好一次、无循环、无轮次。
        step("normalize", do_normalize, summ)
        step("judge", do_judge, summ)
        step("dispose", do_dispose, summ)
        step("output", do_output, summ)
        step("evaluate", do_evaluate, summ)

        ended = self.clock()
        u = ctx.get("unit") or {}
        failed = u.get("parse_status") == "failed"
        decision = ctx.get("decision") or _decision_view(None)
        coverage = ctx.get("coverage") or _coverage_ir(None, ctx["request"], u)
        findings = ctx.get("findings") or []
        disposition = ctx.get("disposition") or _disposition_view(None, decision)
        cp_ran = [] if failed else list(ctx["request"].get("control_points") or [])
        cp_version = self._cp_version(ctx["request"])
        obligations = list(decision.get("obligations") or [])
        iv = decision.get("invariant_violation")
        invariant = ({"code": str(iv), "detail": str(decision.get("error_reason") or "")}
                     if iv else None)
        video = ctx["request"].get("video_sampling")
        if video is not None:
            video = {"interval_ms": video.get("interval_ms"),
                     "total_frames": video.get("total_frames")}

        receipt = {
            "receipt_id": receipt_id,
            "unit_id": u.get("unit_id") or "unknown",
            "skill_id": ctx["request"].get("skill_id") or "unknown",
            "skill_version": ctx["request"].get("skill_version") or "unknown",
            "skill_hash": ctx["request"].get("skill_hash") or "unknown",
            "started_at": _iso(started),
            "ended_at": _iso(ended),
            "steps": steps,
            "skipped": [],
            "rule_snapshot": ctx["request"].get("rule_snapshot") or "unknown",
            "kb_snapshot": ctx["request"].get("kb_snapshot") or "unknown",
            "obligations": obligations,
            "invariant_violation": invariant,
            "control_points_ran": cp_ran,
            "control_points_version": cp_version,
            "video_sampling": video,
            "disposition": {
                "state": disposition.get("state") or decision.get("state"),
                "layer": disposition.get("layer") or decision.get("layer"),
                "release_status": "待放行",
            },
        }
        if ctx["request"].get("model_id"):
            receipt["model_id"] = ctx["request"]["model_id"]

        created_at = _iso(ended)
        ir = {
            "ir_id": "ir-" + _short_hash(
                "review-ir-v1", u.get("unit_id"), created_at),
            "ir_version": "review-ir-v1",
            "source_ir_version": u.get("contract_version") or u.get("unit_id") or "content-unit-v1",
            "content_unit_ref": {
                "unit_id": u.get("unit_id") or "unknown",
                "kind": (u.get("source") or {}).get("kind") or "unknown",
                "parse_status": u.get("parse_status", "ok"),
                **({"failure_kind": u.get("failure_kind")}
                   if u.get("parse_status") == "failed" else {}),
            },
            "findings": findings,
            "decision": {
                "state": decision.get("state"),
                "layer": decision.get("layer"),
                "release_status": "待放行",
                "obligations": obligations,
            },
            "coverage": coverage,
            "receipt_ref": receipt_id,
            "rule_snapshot": ctx["request"].get("rule_snapshot") or "unknown",
            "kb_snapshot": ctx["request"].get("kb_snapshot") or "unknown",
            "control_points_version": cp_version,
            "created_at": created_at,
        }
        if ctx["request"].get("media_fingerprints") is not None:
            ir["media_fingerprints"] = ctx["request"]["media_fingerprints"]

        # 报告 snapshot 的生产装配点：report_render 读的是
        # `snapshot.unknown_bucket_counts`（而不是 decision.unknown_buckets）。
        # 四键恒出现，零也写 0 —— 否则「未知桶为 0」与「没统计」长得一样。
        unknown_counts = {
            axis: int((decision.get("unknown_buckets") or {}).get(axis) or 0)
            for axis in UNKNOWN_BUCKET_KEYS
        }
        failure_counts = {
            kind: (1 if failed and u.get("failure_kind") == kind else 0)
            for kind in FAILURE_KIND_KEYS
        }
        # 回执级：四键计数零也出现；handoff_reason/target_layer 由判定层给出。
        receipt["unknown_buckets"] = unknown_counts
        receipt["unknown_bucket_total"] = sum(unknown_counts.values())
        receipt["handoff_reason"] = decision.get("handoff_reason")
        receipt["target_layer"] = decision.get("target_layer")
        report_snapshot = {
            "ir": ir,
            "failure_kind_counts": failure_counts,
            "unknown_bucket_counts": unknown_counts,
            "evidence": [],
            "unassessed": [],
            "receipt": {
                "skill": receipt["skill_id"],
                "version": receipt["skill_version"],
                "fingerprint": receipt["skill_hash"],
                "skipped_steps": "无",
                "rule_snapshot": receipt["rule_snapshot"],
                # ★ T-451：工作流耗时读数。**算在这里、只算一次** ——
                #   报告（report_render.mjs）与接口（review_api）都按这个键名读，
                #   谁也不许自己再算一份（口径分两处就是两套，迟早各自漂移）。
                #   ★ 用步骤求和而不是 ended_at-started_at：`_iso()` 精度只到秒，
                #     而整条链只跑毫秒级，两个时间戳恒相等 → 秒差恒为 0。
                #     详见 base/workflow_timing.py 的文件头。
                "workflow_timing": _workflow_timing(receipt),
            },
        }

        # ── 运行期契约校验（Playbook §3.3.2 / §3.3.3 / L2-7）──────────
        # 这两个 validator 原先只有定义、没有任何调用点；接在这里是唯一
        # 执行点：每次 run 的 IR/Receipt 必须真的符合 schema 才允许返回。
        # 失败 fail-closed —— 宁可让调用方看到异常，也不安静发出坏回执。
        ir_problems = validate_ir(ir)
        receipt_problems = validate_receipt(receipt)
        if ir_problems or receipt_problems:
            raise ValueError(
                "运行期契约校验失败：IR=%r；Receipt=%r"
                % (ir_problems, receipt_problems))

        return {
            "run_state": "ERROR" if run_state == "ERROR" else decision.get("run_state", "OK"),
            "ir": ir,
            "receipt": receipt,
            "decision": decision,
            "coverage": coverage,
            "findings": findings,
            "external_label": None if failed else decision.get("state"),
            "judge_invoked": bool(ctx.get("judge_invoked")),
            "steps": [s["name"] for s in steps],
            "report_snapshot": report_snapshot,
        }
