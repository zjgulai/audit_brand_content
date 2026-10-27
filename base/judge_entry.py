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


#: 图片/视频单元默认请求的多模态任务。视频的 av_alignment 要 provider 声明
#: audio+video 才谈得上，所以它不在这里 —— 由调用方按 provider 能力追加。
DEFAULT_MEDIA_TASKS = ("scene_semantics",)


def _collect_multimodal_observations(unit, analyze, *, clock=None):
    """产出 L1 观察列表 + 一句说明（说明用于报告里的「未评」措辞）。

    ★ 返回的**永远**是一个 (list, note) 二元组，note 只在「没有观察」时非空：
      · analyze 没注入        → ([], "未接入多模态分析")
      · 载体不是图片/视频      → ([], "本载体无需多模态分析")
      · analyze 抛异常        → ([{"status":"error",...}], "")  ← 落观察，不落空
      · analyze 返回 untested → ([{"status":"untested",...}], "") ← 保留原因

    最后两种情况**必须**落进观察列表而不是返回空：空列表在报告里会被读成
    「画面语义这一节没有内容 = 没问题」。而实际上它恰恰是「没看成」。
    """
    if not callable(analyze):
        return [], "未接入多模态分析"
    source = (unit.get("source") or {}) if isinstance(unit, dict) else {}
    kind = source.get("kind")
    if kind not in ("image", "video"):
        return [], "本载体无需多模态分析"
    tasks = list(DEFAULT_MEDIA_TASKS)
    if kind == "video":
        tasks.append("av_alignment")
    media_ref = {
        "kind": kind,
        "uri": source.get("uri") or unit.get("unit_id") or "inline:unknown",
        "sha256": (unit.get("fingerprint") or {}).get("raw_sha256"),
        "byte_size": source.get("raw_bytes"),
    }
    try:
        raw = analyze(media_ref, tasks)
    except Exception as exc:  # noqa: BLE001
        return ([{
            "status": "error", "task": ",".join(tasks), "statement": "",
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "model": None, "model_version": None,
            "ts": None, "bbox": None, "confidence": None,
            "egress_status": "unknown",
        }], "")
    return _observations_from_result(raw, tasks, clock=clock)


def _observations_from_result(raw, tasks, *, clock=None):
    """把 provider 的返回形状摊平成观察条目。"""
    import time as _time

    now = _time.time() if clock is None else clock()
    created = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime(now))
    if not isinstance(raw, dict):
        return ([{
            "status": "error", "task": ",".join(tasks), "statement": "",
            "reason": "provider 返回的不是对象：%r" % (type(raw).__name__,),
            "model": None, "model_version": None, "ts": None, "bbox": None,
            "confidence": None, "egress_status": "unknown",
        }], "")
    model = raw.get("model")
    overall = raw.get("status")
    entries = []
    per_task = raw.get("tasks") if isinstance(raw.get("tasks"), dict) else {}
    for task in tasks:
        item = per_task.get(task)
        if not isinstance(item, dict):
            # ★ provider 没给这个任务 → 未测，**不许**当成「没有观察」
            entries.append({
                "status": "untested", "task": task, "statement": "",
                "reason": "provider 未返回该任务的结果（overall=%r）" % (overall,),
                "model": model, "model_version": model, "ts": None, "bbox": None,
                "confidence": None, "egress_status": "authorized",
                "created_at": created,
            })
            continue
        status = str(item.get("status") or "untested")
        if status not in ("ok", "untested", "error"):
            status, extra = "error", "未知 status %r" % (status,)
        else:
            extra = ""
        obs_list = item.get("observations") if isinstance(item.get("observations"), list) else []
        if status == "ok" and not obs_list:
            # ok 但空观察 = 自我矛盾，落 untested 而不是 ok
            status = "untested"
            extra = "provider 报 ok 但没有 observations"
        if status != "ok":
            entries.append({
                "status": status, "task": task, "statement": "",
                "reason": str(item.get("reason") or extra or "未说明"),
                "model": model, "model_version": model, "ts": None, "bbox": None,
                "confidence": None, "egress_status": "authorized",
                "created_at": created,
            })
            continue
        for obs in obs_list:
            if not isinstance(obs, dict):
                continue
            statement = str(obs.get("statement") or "").strip()
            if not statement:
                continue
            conf = obs.get("confidence")
            entries.append({
                "status": "ok", "task": task, "statement": statement,
                "reason": "",
                "model": model, "model_version": model,
                "ts": obs.get("timecode"), "bbox": obs.get("region"),
                "confidence": float(conf) if isinstance(conf, (int, float))
                and not isinstance(conf, bool) else None,
                "egress_status": "authorized", "created_at": created,
            })
    return entries, ""


def judge_unit(unit, *, rule_snapshot="rules-v1", kb_snapshot="kb-unavailable",
               skill_id="content-review", skill_version=None,
               skill_hash=None, authority_query=None, clock=None,
               multimodal_analyze=None):
    """把一份 ContentUnit 判成结论。

    ★ T-453：`skill_version` / `skill_hash` 的默认值从「写死的 '1' / 'local'」
      改成 `None` —— `None` 表示**去注册表算**（`base/skill_registry.py`）。

      改之前的样子是本项目一个典型病：回执里那三个字段读起来像「查过了」，
      而实际 `skill_hash` 是 `judge_entry.py:182` 的一个字面量 `"local"`，
      生产链路一个参数都没传。**说不出版本的回执比没有这三个字段更糟。**

      现在：默认走注册表，拿到的指纹是规程文件字节的 sha256。
      调用方显式传值时仍以调用方为准（注入点保留给自检与回放）。

    `multimodal_analyze` 是 T-433 的注入点：`analyze(media_ref, tasks)` 形状的
    可调用对象（通常是 provider 注册表的 `analyze` 包一层）。

    ★ 默认 None = **不做多模态**，此时 `multimodal_observations` 返回空列表 +
      一条 `untested` 说明 —— 而**不是**返回空列表就完事。
      「没有观察」与「看了没问题」在数据上必须长得不一样，否则报告里
      「画面语义」那一节会读成「画面没问题」。这是本项目反复踩的形状。
    """
    if not isinstance(unit, dict):
        raise ValueError("unit 必须是 dict")
    # ★ T-453：未显式给出时，从注册表算。
    if skill_version is None or skill_hash is None:
        from base import skill_registry as _SR
        _fields, _why = _SR.receipt_fields(skill_id)
        if _fields:
            skill_version = skill_version if skill_version is not None else _fields["skill_version"]
            skill_hash = skill_hash if skill_hash is not None else _fields["skill_hash"]
        else:
            # ★ 取不到**不许**编一个好看的默认值（那正是 "local" 的老毛病）。
            #   `untested` 是一个能指认的状态：读的人立刻知道"这一版规程没查到"。
            skill_version = skill_version if skill_version is not None else "untested"
            skill_hash = skill_hash if skill_hash is not None else "untested"
            unit.setdefault("_skill_registry_note", _why)
    observations, observation_note = _collect_multimodal_observations(
        unit, multimodal_analyze, clock=clock)
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
        # T-433：L1 多模态观察 + 一句「为什么没有观察」的说明。
        #
        # ★ note 只在 observations 为空时非空，两者合起来才能表达三态：
        #   有观察（看过了）／空 + note（没看，原因是 X）／空 + 空 note（不可能）。
        #   只交 observations 会让「没接入」与「看了没问题」在调用方看来一样。
        "multimodal_observations": observations,
        "multimodal_note": observation_note,
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
        "report_snapshot": _with_observations(
            result.get("report_snapshot"), observations, observation_note),
    }


def _with_observations(snapshot, observations, note):
    """把 L1 观察塞进冻结的报告快照。

    ★ 为什么在 judge_entry 而不是在 report_render 里现取：
      报告快照是**判定时冻结**的（见 review_reducer 里 report_snapshot 的注释）。
      渲染时再去取一次观察，会让「报告的 IR」与「报告的画面语义」来自两个时刻 ——
      而重审会新增观察。同一个量两个口径是 AGENTS §2.4.8 点名的病。

    ★ 快照为 None 时原样返回 None，不凭观察造一个壳：没有快照就是
      「这份报告渲染不出来」，由发布时拒（ReportStore），不在这里发明。
    """
    if not isinstance(snapshot, dict):
        return snapshot
    out = dict(snapshot)
    out["multimodal_observations"] = list(observations or [])
    out["multimodal_note"] = note or ""
    return out


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
