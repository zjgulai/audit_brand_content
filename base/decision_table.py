#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/decision_table.py —— 唯一判定表（T1-09）

## 唯一性

**判定逻辑只在这里。** 本模块不 import 任何第二个判定实现
（judge_adapter / status_resolver / 其他 decision_*）；Verifier 的 G 段守着这一点。

## 输入

```python
decide({
  "parse_status": "ok" | "partial" | "failed",
  "failure_kind": None | "fetch_error" | "parse_error" | "empty" | "unsupported",
  "coverage_state": "missing" | "partial" | "full",
  "findings": [ {status, severity, authority_state, rule_conflict, ...}, ... ],
  # 以下派生值可选；给了就必须与 findings 算出来的一致（H2 / DERIVED）
  "max_sev": "none"|"L1".."L5",
  "max_sev_authority": "n/a"|"ok"|"missing"|"expired"|"conflict",
  "any_authority_conflict": bool,
  "all_evidence_gaps": [...],
  "has_candidate": bool,
  "rule_conflict": bool,
})
```

## 输出

`run_state` / `state` / `external_label` / `layer` / `obligations` / `max_sev` /
`max_sev_authority` / `any_authority_conflict` / `all_evidence_gaps` /
`has_candidate` / `coverage_incomplete` / `release_status` / `chain` /
`invariant_violation` / `unknown_buckets` / `unknown_bucket_total` /
`handoff_reason` / `target_layer`。

五标签全部 `release_status="待放行"`；`run_state=ERROR` 时
`state` / `external_label` / `layer` / `release_status` 均为 null，
`obligations=["invariant_violation"]`，并记 `invariant_violation=I1..I7`。

## 口径

  - `max_sev` 只由 **status=confirmed** 的 finding 贡献；candidate 不贡献严重度。
  - `L0` 不是最低严重度：confirmed 的 L0 触发 I4 → ERROR（它表示「不知道」）。
  - 链序按 Playbook §3.3.8.1 **严格短路**；partial 永不 PASS。
  - 输入读不出 / 派生值与 findings 不一致 → ERROR，**不得默认 PASS/BLOCK**。
  - 未知桶（Playbook §5.3.3）是**扩展链 16**：`family=未归类` / `scene_domain=其他`
    转 REVIEW/DP3；`authority_source=依据待定` / `consequence=后果未知` 转
    REVIEW/DP4；四类同现取 DP4。未知桶**不得降级已确认 BLOCK**，
    coverage/parse 失败仍先落未审查。四个桶计数每次输出都出现（零也为 0）。
"""
from __future__ import annotations

PARSE_STATUSES = ("ok", "partial", "failed")
FAILURE_KINDS = ("fetch_error", "parse_error", "empty", "unsupported")
COVERAGE_STATES = ("missing", "partial", "full")
STATUSES = ("confirmed", "candidate", "rejected", "superseded")
SEVERITIES = ("L0", "L1", "L2", "L3", "L4", "L5")
AUTHORITY_STATES = ("ok", "missing", "expired", "conflict")

# Playbook §5.3.3：四类未知桶。出现即强制转人工，不得静默落进已知值。
UNKNOWN_BUCKETS = {
    "family": "未归类",
    "scene_domain": "其他",
    "authority_source": "依据待定",
    "consequence": "后果未知",
}
# 依据/后果两轴由法务接手（DP4）；分类/场景缺口由内容审核员接手（DP3）。
UNKNOWN_DP4_AXES = ("authority_source", "consequence")

_SEV_RANK = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4, "L5": 5}
_AUTH_RANK = {"ok": 0, "missing": 1, "expired": 2, "conflict": 3}


def _error(code, detail, base=None):
    b = base or {}
    return {
        "run_state": "ERROR",
        "state": None,
        "external_label": None,
        "layer": None,
        "obligations": ["invariant_violation"],
        "invariant_violation": code,
        "error_reason": detail,
        "max_sev": b.get("max_sev"),
        "max_sev_authority": b.get("max_sev_authority"),
        "any_authority_conflict": b.get("any_authority_conflict"),
        "all_evidence_gaps": b.get("all_evidence_gaps", []),
        "has_candidate": b.get("has_candidate"),
        "coverage_incomplete": b.get("coverage_incomplete"),
        "release_status": None,
        "chain": None,
        "unknown_buckets": _empty_unknown_buckets(),
        "unknown_bucket_total": 0,
        "handoff_reason": None,
        "target_layer": None,
    }


def _derive(findings):
    confirmed = [f for f in findings if f.get("status") == "confirmed"]
    candidates = [f for f in findings if f.get("status") == "candidate"]
    max_sev = "none"
    for f in confirmed:
        sev = f.get("severity")
        if _SEV_RANK.get(sev, -1) > _SEV_RANK.get(max_sev, -1):
            max_sev = sev
    if max_sev == "none":
        max_authority = "n/a"
    else:
        worst = "ok"
        for f in confirmed:
            if f.get("severity") == max_sev:
                auth = f.get("authority_state")
                if _AUTH_RANK.get(auth, 1) > _AUTH_RANK[worst]:
                    worst = auth
        max_authority = worst
    any_conflict = any(f.get("authority_state") == "conflict" for f in confirmed)
    gaps = []
    for i, f in enumerate(confirmed):
        if f.get("authority_state") in ("missing", "expired"):
            gaps.append(f.get("finding_id") or "#%d" % i)
    return {
        "max_sev": max_sev,
        "max_sev_authority": max_authority,
        "any_authority_conflict": any_conflict,
        "all_evidence_gaps": gaps,
        "has_candidate": bool(candidates),
    }


def _empty_unknown_buckets():
    return {axis: 0 for axis in UNKNOWN_BUCKETS}


def _collect_unknown_buckets(inp, findings):
    """统计四类未知桶；只认精确值，不做任何归一/猜测。"""
    counts = _empty_unknown_buckets()
    values = []
    for axis in UNKNOWN_BUCKETS:
        values.append(inp.get(axis))
    for f in findings:
        for axis in UNKNOWN_BUCKETS:
            values.append(f.get(axis))
    counts = {axis: sum(1 for v in values if v == unknown)
              for axis, unknown in UNKNOWN_BUCKETS.items()}
    return counts, sum(counts.values())


def _validate(inp):
    """返回 (normalized_input, None) 或 (None, detail)。"""
    if not isinstance(inp, dict):
        return None, "input_not_dict"
    parse = inp.get("parse_status")
    if parse not in PARSE_STATUSES:
        return None, "bad_parse_status:%r" % (parse,)
    cov = inp.get("coverage_state")
    if cov not in COVERAGE_STATES:
        return None, "bad_coverage_state:%r" % (cov,)
    fk = inp.get("failure_kind")
    if fk is not None and fk not in FAILURE_KINDS:
        return None, "bad_failure_kind:%r" % (fk,)
    findings = inp.get("findings")
    if not isinstance(findings, list):
        return None, "findings_not_list"

    clean = []
    for i, f in enumerate(findings):
        if not isinstance(f, dict):
            return None, "finding_%d_not_dict" % i
        st = f.get("status")
        if st not in STATUSES:
            return None, "finding_%d_bad_status:%r" % (i, st)
        sev = f.get("severity")
        if sev not in SEVERITIES:
            return None, "finding_%d_bad_severity:%r" % (i, sev)
        if st == "confirmed":
            auth = f.get("authority_state")
            if auth not in AUTHORITY_STATES:
                return None, "finding_%d_bad_authority_state:%r" % (i, auth)
        rc = f.get("rule_conflict", False)
        if not isinstance(rc, bool):
            return None, "finding_%d_bad_rule_conflict" % i
        clean.append(f)

    global_rc = inp.get("rule_conflict")
    if global_rc is not None and not isinstance(global_rc, bool):
        return None, "bad_rule_conflict"
    return {"parse": parse, "fk": fk, "coverage": cov,
            "findings": clean, "rule_conflict": global_rc}, None


def _check_invariants(parse, fk, findings, derived, supplied):
    """按 I1–I7 顺序检查；返回违反的编号或 None。"""
    if parse != "failed" and fk is not None:
        return "I1"
    if parse == "failed" and fk is None:
        return "I2"

    max_sev = supplied.get("max_sev", derived["max_sev"])
    max_auth = supplied.get("max_sev_authority", derived["max_sev_authority"])
    any_conf = supplied.get("any_authority_conflict", derived["any_authority_conflict"])
    gaps = supplied.get("all_evidence_gaps", derived["all_evidence_gaps"])

    if (max_sev == "none") != (max_auth == "n/a"):
        return "I3"
    if any(f.get("status") == "confirmed" and f.get("severity") == "L0" for f in findings):
        return "I4"
    if parse == "failed" and findings:
        return "I5"
    if max_auth == "conflict" and not any_conf:
        return "I6"
    if max_sev == "none" and (any_conf or gaps):
        return "I7"
    return None


def decide(inp):
    norm, bad = _validate(inp)
    if bad is not None:
        return _error("INPUT", bad)
    parse, fk, cov = norm["parse"], norm["fk"], norm["coverage"]
    findings = norm["findings"]
    unknown_counts, unknown_total = _collect_unknown_buckets(inp, findings)
    derived = _derive(findings)

    supplied = {}
    for k in ("max_sev", "max_sev_authority", "any_authority_conflict",
              "all_evidence_gaps", "has_candidate"):
        if k in inp:
            supplied[k] = inp[k]
    # 派生值类型校验
    if "max_sev" in supplied and supplied["max_sev"] not in ("none",) + SEVERITIES:
        return _error("INPUT", "bad_max_sev", derived)
    if "max_sev_authority" in supplied and supplied["max_sev_authority"] not in \
            ("n/a",) + AUTHORITY_STATES:
        return _error("INPUT", "bad_max_sev_authority", derived)
    if "any_authority_conflict" in supplied and not isinstance(supplied["any_authority_conflict"], bool):
        return _error("INPUT", "bad_any_authority_conflict", derived)
    if "has_candidate" in supplied and not isinstance(supplied["has_candidate"], bool):
        return _error("INPUT", "bad_has_candidate", derived)
    if "all_evidence_gaps" in supplied and not isinstance(supplied["all_evidence_gaps"], list):
        return _error("INPUT", "bad_all_evidence_gaps", derived)

    violation = _check_invariants(parse, fk, findings, derived, supplied)
    if violation is not None:
        base = dict(derived)
        base["coverage_incomplete"] = cov != "full"
        return _error(violation, "invariant", base)

    # 声明值必须与 findings 算出来的一致（防止拿假数据走链）
    for k, v in supplied.items():
        if v != derived[k]:
            base = dict(derived)
            base["coverage_incomplete"] = cov != "full"
            return _error("DERIVED", "%s declared=%r actual=%r" % (k, v, derived[k]), base)

    max_sev = derived["max_sev"]
    max_auth = derived["max_sev_authority"]
    any_conf = derived["any_authority_conflict"]
    gaps = derived["all_evidence_gaps"]
    has_cand = derived["has_candidate"]
    rule_conflict = norm["rule_conflict"]
    if rule_conflict is None:
        rule_conflict = any(f.get("rule_conflict") is True for f in findings)

    # ── Playbook §3.3.8.1：15 条链，严格短路 ────────────────────────
    if cov == "missing":
        chain, state, layer = 1, "未审查", "DP0"
    elif parse == "failed" and fk == "unsupported":
        chain, state, layer = 2, "未审查", "DP0"
    elif parse == "failed":
        chain, state, layer = 3, "未审查", "DP0"
    elif rule_conflict:
        chain, state, layer = 4, "REVIEW", "DP4"
    elif any_conf:
        chain, state, layer = 5, "REVIEW", "DP4"
    elif max_sev in ("L4", "L5") and max_auth in ("missing", "expired"):
        chain, state, layer = 6, "REVIEW", "DP3"
    elif max_sev in ("L4", "L5") and max_auth == "ok":
        chain, state, layer = 7, "BLOCK", "DP2"
    elif max_sev == "L3" and max_auth in ("missing", "expired"):
        chain, state, layer = 8, "REVIEW", "DP3"
    elif max_sev == "L3" and max_auth == "ok":
        chain, state, layer = 9, "REVIEW", "DP3"
    elif max_sev in ("L1", "L2") and max_auth in ("missing", "expired"):
        chain, state, layer = 10, "REVIEW", "DP3"
    elif cov == "partial":
        chain, state, layer = 11, "REVIEW", "DP3"
    elif parse == "partial":
        chain, state, layer = 12, "REVIEW", "DP3"
    elif has_cand:
        chain, state, layer = 13, "REVIEW", "DP3"
    elif max_sev in ("L1", "L2") and max_auth == "ok":
        chain, state, layer = 14, "待自决", "DP1"
    elif cov == "full" and parse == "ok" and max_sev == "none" and not has_cand:
        chain, state, layer = 15, "PASS", "DP1"
    else:
        # 合法输入域上 15 条链应覆盖全部组合；走到这里说明表漏了一条。
        return _error("NO_CHAIN", "no chain matched", derived)

    # 未知桶只提升「待人工」信号，不降级已确认 BLOCK。
    # 1) parse/coverage 失败已落未审查；2) BLOCK 保持 BLOCK；
    # 3) 其余状态在未知桶出现时转 REVIEW + DP3/DP4。
    handoff_reason = None
    target_layer = None
    if unknown_total and state not in ("BLOCK", "未审查"):
        target_layer = ("DP4" if
                        any(unknown_counts[a] for a in UNKNOWN_DP4_AXES)
                        or layer == "DP4" else "DP3")
        state, layer, chain = "REVIEW", target_layer, 16
        handoff_reason = "unknown_bucket"

    obligations = []
    if state == "BLOCK" and has_cand:
        obligations.append("pending_candidate")
    if state == "BLOCK" and cov == "partial":
        obligations.append("partial_coverage")
    if gaps:
        obligations.append("evidence_gap")
    for axis, count in unknown_counts.items():
        if count:
            obligations.append("unknown_bucket:%s" % axis)

    return {
        "run_state": "OK",
        "state": state,
        "external_label": state,
        "layer": layer,
        "obligations": obligations,
        "invariant_violation": None,
        "max_sev": max_sev,
        "max_sev_authority": max_auth,
        "any_authority_conflict": any_conf,
        "all_evidence_gaps": gaps,
        "has_candidate": has_cand,
        "coverage_incomplete": cov != "full",
        "release_status": "待放行",
        "chain": chain,
        "unknown_buckets": unknown_counts,
        "unknown_bucket_total": unknown_total,
        "handoff_reason": handoff_reason,
        "target_layer": target_layer,
    }
