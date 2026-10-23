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
  I **依据来源类型**（验收表行 22 · SEC-1.1）：`path` → internal、`entry_id` → external，
    分派顺序是生产契约（混合 ref 必须落 internal）；每个分支只回答自己的来源；
    未标来源且不可寻址 → fail-closed。三面探：活行为 / 生产文本 / 导入符号。
    ★ `authority_kind` 显式来源字段：生产代码没有这个行为 —— 行 22 判据的这一半挂
    unfixed，须先在生产实现（不得写恒真断言充数）。
  J **状态计数**（验收表行 35 · KB-6）：counts 给四态各开独立桶（从批次独立重算
    期望逐桶比对，不许一个合并计数、不许漏计）；生产正文逐字钉住；「全记进
    missing / 漏掉计数 / 删桶」三种坏形状用执行证明过不去。

## 退出码

  0 全过 · 1 有红 · 2 未测（导入失败之外的不可测条件）

## 口径

  - 纯离线、纯 stdlib；依据查询用注入的 stub，不联网。
  - 本脚本独立重算状态聚合与路由，不 import 被测模块的期望值常量。
  - 行 22 另读 `base/authority_query.py`（生产文本 + 临时副本对照；external 分支的
    样本用本验证器自有的临时 stub KB，不依赖仓内数据）。行 35 把
    `base/evidence_sync.py` 的生产计数正文逐字抽出执行对照。
"""
from __future__ import annotations

import copy
import json
import os
import re
import sys
import tempfile
import types

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

# ── 行 22 / 行 35 的生产文本路径（只读，永不修改）───────────────────────
AUTH_QUERY_REL = os.path.join("base", "authority_query.py")
EVIDENCE_SYNC_REL = os.path.join("base", "evidence_sync.py")


def _prod_text(rel):
    try:
        with open(os.path.join(ROOT, rel), "rb") as fh:
            return fh.read().decode("utf-8")
    except OSError:
        return None


# 生产分派块原文：path 在前、entry_id 在后（行 22 的变异形状就是把它颠倒）。
DISPATCH_OLD = ('            if ref.get("path"):\n'
                '                return self._query_internal(ref)\n'
                '            if ref.get("entry_id"):\n'
                '                return self._query_external(ref)')
# 生产计数 else 原文：按状态自增（行 35 的变异形状是改成全记 missing）。
COUNT_OLD = ("    for e in enriched:\n"
             "        st = e.get(\"authority_state\")\n"
             "        if st is None:\n"
             "            counts[\"not_computed\"] += 1\n"
             "        else:\n"
             "            counts[st] += 1")

# 坏副本分派块：entry_id 在前（r22a 变异的形状）—— 用来证明行为面真的在读。
DISPATCH_BAD = ('            if ref.get("entry_id"):\n'
                '                return self._query_external(ref)\n'
                '            if ref.get("path"):\n'
                '                return self._query_internal(ref)')

# 坏副本计数循环：全记 missing（r35b 变异的形状）。
COUNT_BAD = ("    for e in enriched:\n"
             "        st = e.get(\"authority_state\")\n"
             "        if st is None:\n"
             "            counts[\"not_computed\"] += 1\n"
             "        else:\n"
             "            counts[\"missing\"] += 1")


def _make_stub_fixtures():
    """本验证器自有的临时夹具（external KB + internal 仓库根），不依赖仓内数据。"""
    body = {"entries": [{
        "id": "VSTUB-001",
        "status": "ratified",
        "clause_no": "STUB-1",
        "变更指纹": "sha256:stub0123456789abcdef",
        "origin": "stated",
    }]}
    root = tempfile.mkdtemp(prefix="evsync-stubfx-")
    kb = os.path.join(root, "stub-kb.json")
    with open(kb, "w", encoding="utf-8") as fh:
        json.dump(body, fh, ensure_ascii=False)
    with open(os.path.join(root, "evsync_i1_fixture.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("line one\nINTERNAL-SOURCE-PROBE-9QF7\nline three\n")
    return root


_STUB_ROOT = None  # 惰性建；见 _stub_root()


def _stub_root():
    global _STUB_ROOT
    if _STUB_ROOT is None:
        _STUB_ROOT = _make_stub_fixtures()
    return _STUB_ROOT


def _load_auq_module(source):
    """把一段 authority_query 源码装成临时模块（__name__ 唯一、不进 sys.modules）。"""
    mod = types.ModuleType("_evsync_auq_copy")
    mod.__file__ = os.path.join(ROOT, AUTH_QUERY_REL)
    exec(compile(source, mod.__file__, "exec"), mod.__dict__)  # noqa: S102
    return mod


def _prod_auq_source():
    """生产 authority_query.py 源码；读不到 → None（I 段落 ⚠ 未测）。"""
    return _prod_text(AUTH_QUERY_REL)


def _load_es_module(source):
    """把一段 evidence_sync 源码装成临时模块（不进 sys.modules、不落盘）。"""
    mod = types.ModuleType("_evsync_es_copy")
    mod.__file__ = os.path.join(ROOT, EVIDENCE_SYNC_REL)
    exec(compile(source, mod.__file__, "exec"), mod.__dict__)  # noqa: S102
    return mod


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
    # A0 先行：合法批次不许抛异常。不加这一层，生产计数一旦崩（如计数桶被删、
    # 自增撞 KeyError），本验证器会跟着 traceback —— mutprobe 判 untested，
    # 生产崩溃对验收不可见（r35a 的形状）。崩了要落红项，不许落 traceback。
    try:
        out = enrich_findings([f_ok], q({"R1": {"state": "ok"}}), RS, KS)
        out_err = ""
    except Exception as exc:  # noqa: BLE001
        out = {"findings": [], "routing": [], "counts": {},
               "rule_snapshot": None, "kb_snapshot": None}
        out_err = "%s: %s" % (type(exc).__name__, exc)
    T("A0 合法批次（confirmed+ok ref）不许抛异常", not out_err, out_err)
    e = out["findings"][0] if out["findings"] else {}
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
    try:
        out2 = enrich_findings([finding("a", refs=[{"ref_id": "R1"}]),
                                finding("b", refs=[{"ref_id": "R2"}])],
                               q({"R1": {"state": "ok"}, "R2": {"state": "expired"}}),
                               RS, KS)
        out2_err = ""
    except Exception as exc:  # noqa: BLE001
        out2 = {"findings": [], "routing": [], "counts": {}}
        out2_err = "%s: %s" % (type(exc).__name__, exc)
    T("E2 每条 finding 都钉住两条快照（且不许抛异常）",
      not out2_err and len(out2["findings"]) == 2
      and all(x.get("rule_snapshot") == RS and x.get("kb_snapshot") == KS
              for x in out2["findings"]), out2_err)

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

    # ── I 依据来源类型（行 22 · SEC-1.1-1/2）：path→internal、entry_id→external ──
    # ★ r22a 的变异把生产 `query()` 里两个分支的先后整个颠倒
    #   （entry_id→external 提到 path→internal 前面）。此后混合 ref 落 external，
    #   分派顺序这个契约没了，而本验证器原先对 authority_query 0 断言 → survived。
    #   ★ 三面探：I1 活行为（混合 ref 的 answer 归谁）、I2 文本（分派块逐字）、
    #   I3 导入符号 —— 只查文本时把两个函数名对调即可过关（r22a 的同族形状）。
    auq_src = _prod_auq_source()
    if auq_src is None:
        T("I0 生产 authority_query.py 可读", False, "读不到（未测，不许当绿）")
    else:
        try:
            auq = _load_auq_module(auq_src)
            stub_root = _stub_root()
            resolver = auq.ExternalStandardsAuthority(
                path=os.path.join(stub_root, "stub-kb.json"),
                repo_root=stub_root)
            # I1 行为面：混合 ref（既有 path 又有 entry_id）必须落 internal ——
            #   internal 分支的 ok 用 `resolved_internal` 自报来源。
            mixed = {"path": "evsync_i1_fixture.txt", "entry_id": "VSTUB-001",
                     "quote": "INTERNAL-SOURCE-PROBE-9QF7"}
            ans_mixed = resolver.query(mixed)
            T("I1 混合 ref（path+entry_id）→ internal 分支（reason=resolved_internal）",
              ans_mixed.get("state") == "ok"
              and ans_mixed.get("reason") == "resolved_internal", str(ans_mixed))
            # 反向面：纯 external ref（无 path）必须落 external 分支（reason=resolved）
            ans_ext = resolver.query({"entry_id": "VSTUB-001",
                                      "article": "STUB-1",
                                      "fingerprint": "sha256:stub0123456789abcdef"})
            T("I1b 纯 external ref → external 分支（reason=resolved）",
              ans_ext.get("state") == "ok" and ans_ext.get("reason") == "resolved",
              str(ans_ext))
            # 坏副本对照：把分派顺序颠倒 → I1 同一探针必须读出变化（不许恒真）。
            bad_src = auq_src.replace(DISPATCH_OLD, DISPATCH_BAD)
            if bad_src == auq_src:
                T("I1c 找不到生产分派块原文（生产代码变了，对照过期）", False, "")
            else:
                bad_auq = _load_auq_module(bad_src)
                bad_resolver = bad_auq.ExternalStandardsAuthority(
                    path=os.path.join(stub_root, "stub-kb.json"),
                    repo_root=stub_root)
                ans_bad = bad_resolver.query(mixed)
                T("I1c 分派顺序打坏后探针必须读到 external（不许恒真）",
                  ans_bad.get("reason") == "resolved", str(ans_bad))
            # I2 文本面：分派块逐字在场（与 I1 同一件契约的第二种读法）
            T("I2 生产分派块逐字在场（path→internal 在 entry_id→external 之前）",
              DISPATCH_OLD in auq_src, "分派块原文不在生产文本里")
            # I3 符号面：两个函数体真的都在
            m_int = re.search(r"def _query_internal\(self, ref\):", auq_src)
            m_ext = re.search(r"def _query_external\(self, ref\):", auq_src)
            T("I3 两个分派函数都在生产文本里",
              bool(m_int) and bool(m_ext),
              "internal=%s external=%s" % (bool(m_int), bool(m_ext)))
            # I4 未寻址 ref：不抛、落 untested（→ missing，fail-closed）
            ans_none = resolver.query({"note": "no address"})
            T("I4 未标来源且不可寻址 → untested（fail-closed，不许当 ok）",
              ans_none.get("state") == "untested", str(ans_none))
        except Exception as e:  # noqa: BLE001
            T("I 段构件跑不起来（未测）", False, "%s: %s" % (type(e).__name__, e))

    # ── J 状态计数（行 35 · KB-6）：四态各一桶、与独立重算逐桶相等 ─────────
    # ★ r35b 的变异把 `counts[st] += 1` 改成 `counts["missing"] += 1` ——
    #   生产在，验证器原先只有一个「counts.ok==1」的单一状态检查 → 别的桶乱记没人看。
    #   ★ 判据用「从批次独立重算期望、逐桶比对」，不是断言某个写死数字。
    counts_in = [
        finding("c1", refs=[{"ref_id": "R1"}]),                 # ok
        finding("c2", refs=[{"ref_id": "R2"}]),                 # missing
        finding("c3", refs=[{"ref_id": "R3"}]),                 # expired
        finding("c4", refs=[{"ref_id": "R4"}]),                 # conflict
        finding("c5", refs=[{"ref_id": "R5"}, {"ref_id": "R6"}]),  # conflict+expired
        finding("c6", status="candidate", refs=[{"ref_id": "R1"}]),  # not_computed
    ]
    counts_q = q({"R1": {"state": "ok"}, "R2": {"state": "missing"},
                  "R3": {"state": "expired"}, "R4": {"state": "conflict"},
                  "R5": {"state": "conflict"}, "R6": {"state": "expired"}})
    # 合法多态批次不许抛异常 —— 生产计数崩了必须落红项（同 A0 的理由）。
    try:
        counts_out = enrich_findings(counts_in, counts_q, RS, KS)
        counts_err = ""
    except Exception as exc:  # noqa: BLE001
        counts_out = {"findings": [], "counts": {}}
        counts_err = "%s: %s" % (type(exc).__name__, exc)
    T("J0 合法多态批次不许抛异常（计数崩了不许变 traceback）",
      not counts_err, counts_err)
    want_counts = {"ok": 0, "missing": 0, "expired": 0, "conflict": 0,
                   "not_computed": 0}
    for _e in counts_out["findings"]:
        st = _e.get("authority_state")
        want_counts[st if st is not None else "not_computed"] += 1
    T("J1 counts 与独立重算逐桶相等（不许漏桶、不许合并）",
      counts_out["counts"] == want_counts,
      "got=%s want=%s" % (json_dumps(counts_out["counts"]),
                          json_dumps(want_counts)))
    T("J1b counts 键恰好五桶（四态 + not_computed）",
      set(counts_out["counts"]) == set(want_counts),
      str(sorted(counts_out["counts"])))
    T("J1c 期望本身非平凡（ok/expired/conflict/missing/not_computed 各 ≥1，"
      "否则 J1 是恒真）",
      all(want_counts[k] >= 1 for k in want_counts), json_dumps(want_counts))

    # J2 文本面：计数循环逐字钉住（计数坏掉而桶仍存在时，J1 的样本形状可能够不着）
    prod_es = _prod_text(EVIDENCE_SYNC_REL)
    T("J2 生产计数循环逐字在场（counts[st] += 1）", prod_es is not None
      and COUNT_OLD in prod_es, "生产计数原文不在 base/evidence_sync.py 里")

    for f in fails:
        print("  ❌ " + f)
    verdict = "❌" if fails else "✅"
    print("\n%s verify_evidence_sync %d 项检查 · %d 项红" % (verdict, checks, len(fails)))
    return 1 if fails else 0


def json_dumps(o):
    return json.dumps(o, ensure_ascii=False)[:300]


# ── --controls：I / J 新断言的反向对照 ─────────────────────────────────
# ★ 断言只验过「好样本绿」是恒真的一半；每条都得指得出「喂什么必须红」。
#   坏样本全部走**临时副本**（exec 到独立模块），生产文件一个字节不动。
def run_controls():
    """返回 (n_pass, n_fail, n_untested)。"""
    ok = fail = untested = 0

    def C(name, cond, detail=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print("  ✅ %s" % name)
        else:
            fail += 1
            print("  ❌ %s  %s" % (name, detail))

    print("verify_evidence_sync · --controls（I/J 新断言的反向对照）")

    src_auq = _prod_auq_source()
    src_es = _prod_text(EVIDENCE_SYNC_REL)
    if src_auq is None or src_es is None:
        print("  ⚠ 未测：生产源码读不到")
        return ok, fail, 1
    stub_root = _stub_root()

    def make_auq(source):
        mod = _load_auq_module(source)
        return mod.ExternalStandardsAuthority(
            path=os.path.join(stub_root, "stub-kb.json"), repo_root=stub_root)

    def make_es(source):
        mod = _load_es_module(source)
        return mod

    # ── C-I1：分派顺序坏副本 → 主检查 I1 的读法必须变红 ────────────────
    bad_disp = src_auq.replace(DISPATCH_OLD, DISPATCH_BAD)
    if bad_disp == src_auq:
        untested += 1
        print("  ⚠ CI1 未测：找不到生产分派块原文（生产代码变了）")
    else:
        try:
            bad = make_auq(bad_disp)
            mixed = {"path": "evsync_i1_fixture.txt", "entry_id": "VSTUB-001",
                     "quote": "INTERNAL-SOURCE-PROBE-9QF7"}
            ans = bad.query(mixed)
            C("CI1 分派打坏后混合 ref 落 external（I1 判据读到红）",
              ans.get("reason") == "resolved", str(ans))
        except Exception as e:  # noqa: BLE001
            C("CI1 坏副本跑不起来", False, str(e))

    # ── C-I2：符号互换坏副本 → 文本面必须红、行为面必须仍红 ─────────────
    #   这是 r22a 的同族形状：两个函数名对调、分派块文本不动。
    swapped = (src_auq.replace("def _query_internal(self, ref):",
                               "def _swapped_query_external(self, ref):")
               .replace("def _query_external(self, ref):",
                        "def _query_internal(self, ref):")
               .replace("def _swapped_query_external(self, ref):",
                        "def _query_external(self, ref):"))
    if swapped == src_auq:
        untested += 1
        print("  ⚠ CI2 未测：找不到两个函数定义原文（生产代码变了）")
    else:
        try:
            sw = make_auq(swapped)
            ans = sw.query({"path": "evsync_i1_fixture.txt",
                            "quote": "INTERNAL-SOURCE-PROBE-9QF7"})
            C("CI2a 函数名互换后 internal ref 实际走 external 判据（不落 resolved_internal）",
              ans.get("reason") != "resolved_internal", str(ans))
        except Exception as e:  # noqa: BLE001
            C("CI2 坏副本跑不起来", False, str(e))

    # ── C-I4：fail-closed 坏副本（未寻址 ref 返回 ok）→ I4 判据必须红 ──
    bad_fc = src_auq.replace(
        '            return {"state": "untested", "reason": "ref_without_address"}',
        '            return {"state": "ok", "reason": "ref_without_address"}')
    if bad_fc == src_auq:
        untested += 1
        print("  ⚠ CI4 未测：找不到 ref_without_address 原文（生产代码变了）")
    else:
        try:
            fc = make_auq(bad_fc)
            ans = fc.query({"note": "no address"})
            C("CI4 fail-open 坏副本下未寻址 ref 报 ok（I4 判据读到红）",
              ans.get("state") == "ok", str(ans))
        except Exception as e:  # noqa: BLE001
            C("CI4 坏副本跑不起来", False, str(e))

    # ── C-J1：计数坏副本（全记 missing）→ J1 构件必须读到逐桶不等 ──────
    bad_cnt = src_es.replace(COUNT_OLD, COUNT_BAD)
    if bad_cnt == src_es:
        untested += 1
        print("  ⚠ CJ1 未测：找不到生产计数循环原文（生产代码变了）")
    else:
        try:
            es_bad = make_es(bad_cnt)
            es_good = make_es(src_es)
            ins = [
                {"finding_id": "k1", "control_code": "H01", "severity": "L4",
                 "status": "confirmed", "quote": "q", "produced_by": "rule",
                 "detected_by": "P0", "authority_ref": [{"ref_id": "R1"}]},
                {"finding_id": "k2", "control_code": "H01", "severity": "L4",
                 "status": "confirmed", "quote": "q", "produced_by": "rule",
                 "detected_by": "P0", "authority_ref": [{"ref_id": "R3"}]},
                {"finding_id": "k3", "control_code": "H01", "severity": "L4",
                 "status": "confirmed", "quote": "q", "produced_by": "rule",
                 "detected_by": "P0", "authority_ref": [{"ref_id": "R4"}]},
            ]
            qmap = {"R1": {"state": "ok"}, "R3": {"state": "expired"},
                    "R4": {"state": "conflict"}}
            out = es_bad.enrich_findings(ins, _ctl_q(qmap), "rs", "ks")
            want = {"ok": 1, "missing": 0, "expired": 1, "conflict": 1,
                    "not_computed": 0}
            C("CJ1 计数打坏后 counts 与独立重算逐桶不等（J1 判据读到红）",
              out["counts"] != want, json_dumps(out["counts"]))
            C("CJ2 好副本同一批 counts 逐桶相等（反向面不许恒红）",
              _ctl_counts_ok(es_good, ins, qmap, want))
        except Exception as e:  # noqa: BLE001
            C("CJ1 坏副本跑不起来", False, str(e))

    # ── C-J3：多出一个合并桶的坏副本 → J1b 键集合判据必须红 ────────────
    bad_extra = src_es.replace(
        '    counts["not_computed"] = 0',
        '    counts["not_computed"] = 0\n    counts["merged"] = 0')
    if bad_extra == src_es:
        untested += 1
        print("  ⚠ CJ3 未测：找不到计数初始化原文（生产代码变了）")
    else:
        try:
            es_extra = make_es(bad_extra)
            ins = [{"finding_id": "k1", "control_code": "H01", "severity": "L4",
                    "status": "confirmed", "quote": "q", "produced_by": "rule",
                    "detected_by": "P0", "authority_ref": [{"ref_id": "R1"}]}]
            out = es_extra.enrich_findings(ins, _ctl_q({"R1": {"state": "ok"}}),
                                           "rs", "ks")
            C("CJ3 多出合并桶后键集合不再恰好五桶（J1b 判据读到红）",
              "merged" in out["counts"] and set(out["counts"]) !=
              {"ok", "missing", "expired", "conflict", "not_computed"},
              json_dumps(out["counts"]))
        except Exception as e:  # noqa: BLE001
            C("CJ3 坏副本跑不起来", False, str(e))

    # ── C-J4：删桶坏副本（r35a 形状，自增时 KeyError 崩）→ J0 防崩壳必须接住 ──
    #   ★ 这个形状不能直接喂给 enrich_findings 裸跑（会崩，mutprobe 判 untested）；
    #   这里验的是「J0 的 try/except 壳」对同一形状确实落红项而非 traceback。
    bad_del = src_es.replace('    counts["not_computed"] = 0',
                             '    counts["not_computed"] = 0\n'
                             '    del counts["ok"]')
    if bad_del == src_es:
        untested += 1
        print("  ⚠ CJ4 未测：找不到计数初始化原文（生产代码变了）")
    else:
        try:
            es_del = make_es(bad_del)
            ins = [{"finding_id": "k1", "control_code": "H01", "severity": "L4",
                    "status": "confirmed", "quote": "q", "produced_by": "rule",
                    "detected_by": "P0", "authority_ref": [{"ref_id": "R1"}]}]
            guard_err = ""
            try:
                es_del.enrich_findings(ins, _ctl_q({"R1": {"state": "ok"}}),
                                       "rs", "ks")
            except Exception as exc:  # noqa: BLE001
                guard_err = "%s: %s" % (type(exc).__name__, exc)
            C("CJ4 删桶副本在 J0 防崩壳下落红项（KeyError 被接住，不外泄）",
              guard_err.startswith("KeyError"), guard_err or "没抛（坏样本没坏？）")
        except Exception as e:  # noqa: BLE001
            C("CJ4 坏副本跑不起来", False, str(e))

    # ── 好样本正向面：原版生产必须让 I1/I2/I4/J 的构件全绿 ─────────────
    try:
        good = make_auq(src_auq)
        mixed = {"path": "evsync_i1_fixture.txt", "entry_id": "VSTUB-001",
                 "quote": "INTERNAL-SOURCE-PROBE-9QF7"}
        C("CG1 好样本：混合 ref 落 internal（I1 不误报）",
          good.query(mixed).get("reason") == "resolved_internal", "")
        C("CG2 好样本：纯 external 落 external（I1b 不误报）",
          good.query({"entry_id": "VSTUB-001", "article": "STUB-1",
                      "fingerprint": "sha256:stub0123456789abcdef"}
                     ).get("reason") == "resolved", "")
        C("CG3 好样本：分派块文本在场（I2 不误报）",
          DISPATCH_OLD in src_auq, "")
        C("CG4 好样本：计数循环文本在场（J2 不误报）",
          COUNT_OLD in src_es, "")
    except Exception as e:  # noqa: BLE001
        C("CG 好样本构件跑不起来（未测）", False, str(e))
        untested += 1

    print("\n%s --controls %d 过 · %d 红 · %d 未测"
          % ("✅" if fail == 0 else "❌", ok, fail, untested))
    return ok, fail, untested


def _ctl_q(mapping):
    """--controls 用的查询桩（与主检查的 q() 同形状，独立定义便于坏副本复用）。"""
    def query(ref):
        rid = ref.get("ref_id") if isinstance(ref, dict) else None
        v = mapping.get(rid)
        if isinstance(v, Exception):
            raise v
        return v if v is not None else {"state": "missing", "reason": "not_found"}
    return query


def _ctl_counts_ok(es_mod, findings, mapping, want):
    """好副本上跑同一批，断言 counts 逐桶相等。"""
    out = es_mod.enrich_findings(findings, _ctl_q(mapping), "rs", "ks")
    return out["counts"] == want


def _usage():
    print("用法：python3 tools/verify_evidence_sync.py [--controls]")


if __name__ == "__main__":
    if "--controls" in sys.argv:
        _ok, _fail, _untested = run_controls()
        sys.exit(1 if _fail else (2 if (_untested and not _ok) else 0))
    if any(a.startswith("-") and a not in ("--controls", "-h", "--help")
           for a in sys.argv[1:]):
        _usage()
        sys.exit(2)
    sys.exit(main())
