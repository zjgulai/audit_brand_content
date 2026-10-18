#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_evidence_sync.py —— `base/evidence_sync.py` 的判据（T1-06）

## 它验什么

  A **enrich**：confirmed finding 得到 `authority_state`，两条快照被钉住；
    不改原 finding、不新增 finding_id、不产新 finding。
  B **ref 级六态 → finding 级四值**：ok/missing/expired/conflict/untested/disabled
    按固定口径聚合；untested/disabled 压成 missing（**不许 fail-open**）。
  C **三分法路由**：missing/expired → DP3；conflict → DP4；ok → 不放行也不转人。
  D **机结资格**：`may_block()` 只在 authority_state=ok 且 rule_conflict=false 时为真；
    缺失/过期/冲突/字段缺失一律 False。
  E **快照**：rule_snapshot / kb_snapshot 必须非空并逐条钉在 finding 上；空 → 拒。
  F **范围**：不判 state/layer、不写回执、不产 finding；非 confirmed 不要求 authority_state。
  G **反向对照**：missing 当 ok、冲突与过期同码、查不到依据仍可 BLOCK、kb 快照为空
    —— 四种坏样本必须红。

## 退出码

  0 全过 · 1 有红 · 2 未测（导入失败之外的不可测条件）

## 口径

  - 纯离线、纯 stdlib；依据查询用注入的 stub，不联网。
  - 本脚本独立重算状态聚合与路由，不 import 被测模块的期望值常量。
"""
from __future__ import annotations

import copy
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "base"))

try:
    from evidence_sync import (
        AUTHORITY_STATES, REF_STATES, InvalidSnapshot,
        aggregate_authority, collapse_ref_state, enrich_finding, enrich_findings,
        may_block, route_for)
except Exception as e:  # noqa: BLE001
    print("❌ 导入 base/evidence_sync.py 失败：%s" % e)
    sys.exit(1)

ALLOWED_NEW = {"authority_state", "rule_conflict", "rule_snapshot",
               "kb_snapshot", "resolution_detail"}


def finding(fid="f1", status="confirmed", refs=None):
    f = {
        "finding_id": fid,
        "control_code": "H01",
        "severity": "L4",
        "status": status,
        "quote": "cure",
        "produced_by": "rule",
        "detected_by": "P0",
    }
    if refs is not None:
        f["authority_ref"] = refs
    return f


def main():
    fails = []
    checks = 0

    def T(cid, ok, detail=""):
        nonlocal checks
        checks += 1
        if not ok:
            fails.append("%s  %s" % (cid, detail))

    def q(mapping):
        def query(ref):
            rid = ref.get("ref_id") if isinstance(ref, dict) else None
            v = mapping.get(rid)
            if isinstance(v, Exception):
                raise v
            return v if v is not None else {"state": "missing", "reason": "not_found"}
        return query

    RS, KS = "rule-snap-1", "kb-snap-1"

    # ── A enrich 基本契约 ────────────────────────────────────────────
    f_ok = finding(refs=[{"ref_id": "R1"}])
    orig = copy.deepcopy(f_ok)
    out = enrich_findings([f_ok], q({"R1": {"state": "ok"}}), RS, KS)
    e = out["findings"][0]
    T("A1 confirmed 得到 authority_state=ok", e.get("authority_state") == "ok",
      str(e.get("authority_state")))
    T("A2 rule_conflict=false", e.get("rule_conflict") is False, str(e.get("rule_conflict")))
    T("A3 两条快照被钉住", e.get("rule_snapshot") == RS and e.get("kb_snapshot") == KS,
      "%s / %s" % (e.get("rule_snapshot"), e.get("kb_snapshot")))
    T("A4 输入 finding 未被原地修改", f_ok == orig, str(f_ok))
    T("A5 没有新增 finding_id / 没有产新 finding",
      e.get("finding_id") == "f1" and len(out["findings"]) == 1, str(out["findings"]))
    T("A6 只新增允许的字段",
      set(e) - set(orig) <= ALLOWED_NEW, str(set(e) - set(orig)))
    T("A7 counts.ok == 1 且 routing 一条", out["counts"].get("ok") == 1
      and len(out["routing"]) == 1, json_dumps(out))

    # ── B ref 六态 → finding 四值 ───────────────────────────────────
    for raw, want in (("missing", "missing"), ("untested", "missing"), ("disabled", "missing"),
                      ("expired", "expired"), ("conflict", "conflict"), ("ok", "ok")):
        got = collapse_ref_state(raw)
        T("B1 collapse %s → %s" % (raw, want), got == want, got)

    cases = [
        ("missing", [{"state": "missing"}], "missing"),
        ("untested", [{"state": "untested"}], "missing"),
        ("disabled", [{"state": "disabled"}], "missing"),
        ("expired", [{"state": "expired"}], "expired"),
        ("conflict", [{"state": "conflict"}], "conflict"),
        ("ok+ok", [{"state": "ok"}, {"state": "ok"}], "ok"),
        ("ok+missing", [{"state": "ok"}, {"state": "missing"}], "missing"),
        ("expired+missing", [{"state": "expired"}, {"state": "missing"}], "expired"),
        ("conflict+expired", [{"state": "conflict"}, {"state": "expired"}], "conflict"),
        ("无依据", [], "missing"),
    ]
    for name, states, want in cases:
        got = aggregate_authority(states)
        T("B2 aggregate %s → %s" % (name, want), got == want, got)

    # 多 ref 聚合走 enrich 一次，确认不是只测纯函数
    f_mix = finding(refs=[{"ref_id": "R1"}, {"ref_id": "R2"}])
    e_mix = enrich_finding(f_mix, q({"R1": {"state": "conflict"}, "R2": {"state": "expired"}}), RS, KS)
    T("B3 多 ref conflict+expired → finding=conflict",
      e_mix["authority_state"] == "conflict", str(e_mix["authority_state"]))

    # ── C 三分法路由 ────────────────────────────────────────────────
    T("C1 missing → DP3", route_for("missing") == "DP3", str(route_for("missing")))
    T("C2 expired → DP3", route_for("expired") == "DP3", str(route_for("expired")))
    T("C3 conflict → DP4", route_for("conflict") == "DP4", str(route_for("conflict")))
    T("C4 ok → 不转人（None）", route_for("ok") is None, str(route_for("ok")))
    T("C5 未知状态不 fail-open（返回 DP3 或抛错，不许 None）",
      route_for("bogus") in ("DP3", "DP4"), str(route_for("bogus")))

    # ── D 机结资格 ──────────────────────────────────────────────────
    T("D1 ok 且 rule_conflict=false → 可 BLOCK",
      may_block({"authority_state": "ok", "rule_conflict": False}) is True, "")
    for st in ("missing", "expired", "conflict"):
        T("D2 %s → 不可 BLOCK" % st,
          may_block({"authority_state": st, "rule_conflict": False}) is False, "")
    T("D3 authority_state 缺失 → 不可 BLOCK", may_block({}) is False, "")
    T("D4 rule_conflict 缺失 → 不可 BLOCK",
      may_block({"authority_state": "ok"}) is False, "")
    T("D5 rule_conflict=true 即使 authority_state=ok → 不可 BLOCK",
      may_block({"authority_state": "ok", "rule_conflict": True}) is False, "")

    # ── E 快照 ──────────────────────────────────────────────────────
    for name, rs, ks in (("kb 空", RS, ""), ("rule 空", "", KS),
                         ("kb None", RS, None), ("rule None", None, KS)):
        try:
            enrich_finding(finding(refs=[{"ref_id": "R1"}]), q({"R1": {"state": "ok"}}), rs, ks)
            T("E1 %s → 必须拒" % name, False, "未拒")
        except InvalidSnapshot:
            T("E1 %s → 必须拒" % name, True, "")
    out2 = enrich_findings([finding("a", refs=[{"ref_id": "R1"}]),
                            finding("b", refs=[{"ref_id": "R2"}])],
                           q({"R1": {"state": "ok"}, "R2": {"state": "expired"}}), RS, KS)
    T("E2 每条 finding 都钉住两条快照",
      all(x.get("rule_snapshot") == RS and x.get("kb_snapshot") == KS for x in out2["findings"]), "")

    # ── F 范围：非 confirmed / 不越界 ───────────────────────────────
    for st in ("candidate", "rejected", "superseded"):
        ec = enrich_finding(finding(status=st, refs=[{"ref_id": "R1"}]),
                            q({"R1": {"state": "ok"}}), RS, KS)
        T("F1 %s 不要求 authority_state（None）" % st, ec.get("authority_state") is None,
          str(ec.get("authority_state")))
        T("F1b %s 不可 BLOCK" % st, may_block(ec) is False, "")
    forbidden = {"state", "layer", "obligations", "receipt", "run_state"}
    T("F2 enrich 不越界写 state/layer/obligations",
      not (set(e) & forbidden), str(set(e) & forbidden))
    T("F3 结果里不含新 finding 列表以外的产物",
      set(out.keys()) == {"findings", "routing", "counts", "rule_snapshot", "kb_snapshot"},
      str(sorted(out.keys())))

    # ── G 查询失败 / 未知状态 → 一律 fail-closed ───────────────────
    e_fail = enrich_finding(finding(refs=[{"ref_id": "R1"}]),
                            q({"R1": RuntimeError("kb down")}), RS, KS)
    T("G1 查询抛异常 → missing（不是 ok）", e_fail["authority_state"] == "missing",
      str(e_fail["authority_state"]))
    T("G1b 查询异常 → 不可 BLOCK", may_block(e_fail) is False, "")
    T("G1c 查询异常 → 路由 DP3", route_for(e_fail["authority_state"]) == "DP3", "")
    e_unknown = enrich_finding(finding(refs=[{"ref_id": "R1"}]),
                               q({"R1": {"state": "bogus"}}), RS, KS)
    T("G2 未知 ref 状态 → missing（不许当 ok）", e_unknown["authority_state"] == "missing",
      str(e_unknown["authority_state"]))
    e_noref = enrich_finding(finding(refs=None), q({}), RS, KS)
    T("G3 无 authority_ref → missing", e_noref["authority_state"] == "missing",
      str(e_noref["authority_state"]))
    T("G3b 无 authority_ref → 不可 BLOCK", may_block(e_noref) is False, "")

    # ── H 反向对照：把修复删掉必须红 ────────────────────────────────
    T("H1 missing 不得被聚合为 ok（删映射即红）",
      aggregate_authority([{"state": "missing"}]) != "ok", "")
    T("H2 conflict 与 expired 同码 → 按 conflict（顺序反过来也必须是 conflict）",
      aggregate_authority([{"state": "expired"}, {"state": "conflict"}]) == "conflict"
      and aggregate_authority([{"state": "conflict"}, {"state": "expired"}]) == "conflict", "")
    T("H3 查不到依据仍可 BLOCK 必须红（may_block 必须 False）",
      may_block({"authority_state": "missing", "rule_conflict": False}) is False, "")
    try:
        enrich_findings([finding()], q({}), RS, "")
        T("H4 kb_snapshot 为空 → 必须红", False, "未拒")
    except InvalidSnapshot:
        T("H4 kb_snapshot 为空 → 必须红", True, "")
    T("H5 REF_STATES / AUTHORITY_STATES 取值集合正确",
      set(REF_STATES) == {"ok", "missing", "expired", "conflict", "untested", "disabled"}
      and set(AUTHORITY_STATES) == {"ok", "missing", "expired", "conflict"},
      "%s / %s" % (sorted(REF_STATES), sorted(AUTHORITY_STATES)))

    for f in fails:
        print("  ❌ " + f)
    verdict = "❌" if fails else "✅"
    print("\n%s verify_evidence_sync %d 项检查 · %d 项红" % (verdict, checks, len(fails)))
    return 1 if fails else 0


def json_dumps(o):
    import json
    return json.dumps(o, ensure_ascii=False)[:300]


if __name__ == "__main__":
    sys.exit(main())
