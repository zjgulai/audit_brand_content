#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生产判定入口：ContentUnit → Orchestrator(rule_judge) → 五标签/回执。

ADR-0016 的唯一生产判定引擎是 base/rule_judge.py；旧 skeleton/judge.py 只作分析。
本入口不下载媒体、不做 OCR，只接收已经归一化好的 ContentUnit。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base import coverage_composer as CC  # noqa: E402
from base import evidence_sync as ES  # noqa: E402
from base.control_points import ControlPointRegistry  # noqa: E402
from base.orchestrator import Orchestrator  # noqa: E402
from base.rule_judge import RuleJudge  # noqa: E402

CONTRACT_VERSION = "judge-entry-v1"


def _finding_id(unit_id, hit):
    body = json.dumps({
        "unit_id": unit_id,
        "control_code": hit["control_code"],
        "rule_key": hit["rule_key"],
        "start": hit["start"], "end": hit["end"],
        "quote": hit["quote"],
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "f-" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:20]


def _draft_findings(unit, hits, registry):
    out = []
    for hit in hits:
        control = registry.get_active(hit["control_code"])
        out.append({
            "finding_id": _finding_id(unit["unit_id"], hit),
            "control_code": hit["control_code"],
            "rule_key": hit["rule_key"],
            "status": "confirmed",
            "severity": hit["severity"],
            "produced_by": "rule",
            "derived_from": None,
            "detected_by": hit["detected_by"],
            "quote": hit["quote"],
            "location": {
                "kind": "text_span", "start": hit["start"],
                "end": hit["end"], "quote": hit["quote"],
            },
            "authority_ref": list(control.get("authority_ref") or []),
        })
    return out


def _local_authority_query(_ref):
    """默认没有外部依据查询器：未测必须压成 missing，绝不凭登记字段 fail-open。"""
    return {"state": "untested", "reason": "authority_query_not_wired"}


def judge_unit(unit, *, rule_snapshot="rules-v1", kb_snapshot="kb-unavailable",
               skill_id="content-review", skill_version="1",
               skill_hash="local", authority_query=None, clock=None):
    if not isinstance(unit, dict):
        raise ValueError("unit 必须是 dict")
    registry = ControlPointRegistry()
    engine = RuleJudge(registry)
    query = authority_query or _local_authority_query

    active_codes = sorted(registry.active_codes())
    active_families = {
        registry.get_active(code).get("family") for code in active_codes
    }

    def rule_component(ctx):
        hits = engine.judge(ctx["unit"], control_codes=active_codes)
        return _draft_findings(ctx["unit"], hits, registry)

    def evidence_component(ctx):
        return ES.enrich_findings(
            ctx["findings"], query, rule_snapshot, kb_snapshot)["findings"]

    def coverage_component(ctx):
        current = ctx["unit"]
        textification = current.get("textification") or {}
        codes = sorted({f["control_code"] for f in ctx["findings"]})
        by_family = {
            family: ("ran" if family in active_families else "not_run")
            for family in CC.load_all_families()
        }
        reasons = []
        return CC.compose_and_derive(
            modalities_evaluated=[(current.get("source") or {}).get("kind") or "unknown"],
            rules_version={"version": rule_snapshot,
                           "fingerprint": engine.rule_snapshot_sha256},
            control_points_by_family=by_family,
            not_run_reasons=reasons,
            does_not_cover=list(textification.get("does_not_cover") or []),
            parse_status=current.get("parse_status", "ok"),
        )

    media_fingerprints = None
    if (unit.get("source") or {}).get("kind") in ("image", "video"):
        fp = unit.get("fingerprint") or {}
        extractor = str((unit.get("textification") or {}).get("extractor") or "unknown")
        media_fingerprints = {
            "frame_manifest_hash": str(fp.get("raw_sha256") or "unknown"),
            "ocr_output_hash": str(fp.get("text_sha256") or "unknown"),
            "asr_output_hash": "not_available",
            "model_config_hash": hashlib.sha256(
                (CONTRACT_VERSION + "|" + extractor).encode("utf-8")).hexdigest(),
        }

    request = {
        "unit": unit,
        "control_points": active_codes,
        "control_points_version": registry.table_version,
        "rule_snapshot": rule_snapshot,
        "kb_snapshot": kb_snapshot,
        "rules_version": {"version": rule_snapshot,
                          "fingerprint": engine.rule_snapshot_sha256},
        "modalities_evaluated": [(unit.get("source") or {}).get("kind") or "unknown"],
        "does_not_cover": list((unit.get("textification") or {}).get("does_not_cover") or []),
        "skill_id": skill_id,
        "skill_version": skill_version,
        "skill_hash": skill_hash,
        "media_fingerprints": media_fingerprints,
    }
    result = Orchestrator(
        rule_judge=rule_component,
        semantic_judge={"status": "untested", "findings": []},
        evidence=evidence_component,
        coverage=coverage_component,
        control_points_version=registry.table_version,
        clock=clock,
    ).run(request, unit=unit)
    return {
        "contract_version": CONTRACT_VERSION,
        "label": result["decision"]["state"],
        "layer": result["decision"]["layer"],
        "release_status": result["decision"]["release_status"],
        "findings": result["ir"]["findings"],
        "ir": result["ir"],
        "receipt": result["receipt"],
        "steps": result["steps"],
        "run_state": result["run_state"],
        # T-316b: report render input, previously dropped here.
        #
        # Orchestrator.run() always builds result["report_snapshot"] and returns
        # it (single return at the end of run(); verified 2026-10-24), but this
        # return dict did not carry it — so ReportStore never received render
        # input anywhere in the production chain, while the report verifiers
        # stayed green (they only exercise ReportStore itself).
        #
        # Why .get() and not a hard index: today run() has exactly one return
        # and it always carries the key, so .get() buys nothing *now*. It is
        # kept as a documented seam — if a future early-return path is added,
        # downstream gets None (a case it must already handle, since the reducer
        # decides whether a payload without a snapshot may be ingested) instead
        # of a KeyError surfacing as "process crashed" during a review.
        # ★ Do not read this as "ERROR path yields None" — measured false.
        "report_snapshot": result.get("report_snapshot"),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--unit", help="ContentUnit JSON 文件")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        # 完整行为自证在 tools/verify_judge_entry.py；base 总门调用同一验证器。
        import subprocess
        verifier = ROOT / "tools" / "verify_judge_entry.py"
        return subprocess.run([sys.executable, str(verifier)], cwd=ROOT).returncode
    if not args.unit:
        ap.error("--unit 必填（除非 --selftest）")
    unit = json.loads(Path(args.unit).read_text(encoding="utf-8"))
    result = judge_unit(unit)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("%s / %s · findings=%d" % (
            result["label"], result["layer"], len(result["findings"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
