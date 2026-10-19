#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_decision_table.py —— `base/decision_table.py` 的判据（T1-09）

## 它验什么

  A **15 条链逐条可达**：按 Playbook §3.3.8.1 的顺序构造 15 个样本，
    断言 `chain` / `state` / `layer` 与表逐格一致。
  B **顺序即裁决**：coverage missing 先于一切；解析失败先于规则冲突；
    规则冲突先于 BLOCK；依据冲突先于 BLOCK；L4/L5 先于 partial；
    partial 先于 PASS。
  C **candidate / L0 / partial**：candidate L5 单独 → REVIEW 而非 BLOCK；
    candidate 不贡献 max_sev；L0 confirmed → ERROR(I4)；partial 干净 → REVIEW 且 coverage_incomplete。
  D **I1–I7**：每条不变量各一个坏样本 → ERROR、state/external_label=null、
    不得默认 PASS/BLOCK；obligations 含 invariant_violation。
  E **并行义务**：BLOCK+candidate → pending_candidate；BLOCK+partial → partial_coverage；
    evidence gaps → evidence_gap；空数组不省略。
  F **输出契约**：五标签全部 release_status=待放行；明确标签有 external_label；
    ERROR 时 external_label=null；不读不出就默认 PASS/BLOCK。
  G **唯一实现**：`base/decision_table.py` 不 import 第二个判定实现
    （judge_adapter / status_resolver / 其他 decision_*）。
  H **反向对照**：改链序、去 I1–I7、candidate 计严重度、partial 放 PASS、
    去掉 release_status —— 验证器必须红（源码变异由外部执行，本脚本守住断言）。

## 退出码

  0 全过 · 1 有红 · 2 未测（导入失败之外的不可测条件）
"""
from __future__ import annotations

import ast
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "base"))

try:
    from decision_table import decide
except Exception as e:  # noqa: BLE001
    print("❌ 导入 base/decision_table.py 失败：%s" % e)
    sys.exit(1)

FIVE_STATES = {"BLOCK", "REVIEW", "未审查", "待自决", "PASS"}
LAYERS = {"DP0", "DP1", "DP2", "DP3", "DP4"}

# ── C-46 / L2-1a：判定逻辑唯一性全仓扫描 ───────────────────────────────
# 扫描范围刻意是产品运行时代码（base/api/tools），不含 skill/ 知识库技能、
# tests/、verifiers 自身与临时/诊断脚本 —— 后者本来就可以写标签样例。
SCAN_ROOTS = ("base", "api", "tools")
SCAN_SKIP_DIRS = {".git", ".venv", ".venv-r4", "node_modules", "__pycache__",
                  "skills", ".vendor", ".playwright-mcp"}
SCAN_SKIP_BASENAMES = ("verify_", "test_", "smoke_", "probe_")
SCAN_WHITELIST = {
    # 目前唯一命中：parse_status=failed 的契约回退。
    "base/orchestrator.py": (
        "parse_status=failed 时 judge 不被调用，按 Playbook 链 3 把 "
        "decision/disposition 固定为 未审查/DP0；这是编排器契约回退，"
        "不是第二套 15 链判定。若后续把该回退收进 decision_table，本白名单应删除。"
    ),
}
DECISION_FIELDS = {"state", "external_label", "layer"}


def F(fid="f1", status="confirmed", sev="L4", auth="ok", rc=False):
    return {
        "finding_id": fid, "control_code": "H01", "status": status,
        "severity": sev, "authority_state": auth, "rule_conflict": rc,
        "quote": "cure", "produced_by": "rule", "detected_by": "P0",
    }


def inp(**over):
    x = {
        "parse_status": "ok", "failure_kind": None,
        "coverage_state": "full", "findings": [], "rule_conflict": False,
    }
    x.update(over)
    return x


def _scan_excluded(rel):
    if rel == "base/decision_table.py":
        return True
    parts = rel.split("/")
    if any(p in SCAN_SKIP_DIRS for p in parts):
        return True
    base = os.path.basename(rel)
    if base.startswith(SCAN_SKIP_BASENAMES) or base.endswith("_test.py"):
        return True
    if rel.startswith("tests/"):
        return True
    return False


def _allowed(field, node):
    values = LAYERS if field == "layer" else FIVE_STATES
    return isinstance(node, ast.Constant) and isinstance(node.value, str) \
        and node.value in values


def decision_writes_in_text(text):
    """返回 [(lineno, field)]：命中「状态/层/对外标签被写成五标签或 DP 值」。"""
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return [("syntax", e.lineno or 0)]
    hits = []

    class V(ast.NodeVisitor):
        def visit_Assign(self, node):
            for target in node.targets:
                name = None
                if isinstance(target, ast.Name):
                    name = target.id
                elif isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant):
                    name = target.slice.value
                if name in DECISION_FIELDS:
                    v = node.value
                    if _allowed(name, v) or (isinstance(v, ast.IfExp)
                                             and (_allowed(name, v.body)
                                                  or _allowed(name, v.orelse))):
                        hits.append((node.lineno, name))
            self.generic_visit(node)

        def visit_AnnAssign(self, node):
            if isinstance(node.target, ast.Name) and node.target.id in DECISION_FIELDS \
                    and node.value is not None and _allowed(node.target.id, node.value):
                hits.append((node.lineno, node.target.id))
            self.generic_visit(node)

        def visit_Dict(self, node):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value in DECISION_FIELDS:
                    if _allowed(k.value, v) or (isinstance(v, ast.IfExp)
                                                and (_allowed(k.value, v.body)
                                                     or _allowed(k.value, v.orelse))):
                        hits.append((node.lineno, k.value))
            self.generic_visit(node)

    V().visit(tree)
    return hits


def decision_writes_in_file(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return decision_writes_in_text(f.read())
    except OSError:
        return [("unreadable", 0)]


def scan_decision_logic():
    scanned = []
    hits = {}
    for root in SCAN_ROOTS:
        for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, root)):
            dirnames[:] = [d for d in dirnames if d not in SCAN_SKIP_DIRS]
            for name in filenames:
                if not name.endswith(".py"):
                    continue
                rel = os.path.relpath(os.path.join(dirpath, name), ROOT)
                if _scan_excluded(rel):
                    continue
                scanned.append(rel)
                found = decision_writes_in_file(os.path.join(ROOT, rel))
                if found:
                    hits[rel] = found
    return scanned, hits


def main():
    fails = []
    checks = 0

    def T(cid, ok, detail=""):
        nonlocal checks
        checks += 1
        if not ok:
            fails.append("%s  %s" % (cid, detail))

    def chk(cid, x, chain, state, layer):
        r = decide(x)
        T(cid, r.get("run_state") == "OK" and r.get("chain") == chain
          and r.get("state") == state and r.get("layer") == layer
          and r.get("external_label") == state,
          "chain=%r state=%r layer=%r ext=%r run=%r"
          % (r.get("chain"), r.get("state"), r.get("layer"),
             r.get("external_label"), r.get("run_state")))
        return r

    # ── A 15 条链逐条可达 ────────────────────────────────────────────
    chk("A01 链1 coverage missing", inp(coverage_state="missing", findings=[F()]),
        1, "未审查", "DP0")
    chk("A02 链2 failed+unsupported",
        inp(parse_status="failed", failure_kind="unsupported", findings=[]),
        2, "未审查", "DP0")
    chk("A03 链3 failed+empty",
        inp(parse_status="failed", failure_kind="empty", findings=[]),
        3, "未审查", "DP0")
    chk("A04 链4 rule_conflict", inp(findings=[F(sev="L2")], rule_conflict=True),
        4, "REVIEW", "DP4")
    chk("A05 链5 any authority conflict",
        inp(findings=[F("a", sev="L4", auth="ok"), F("b", sev="L2", auth="conflict")]),
        5, "REVIEW", "DP4")
    chk("A06 链6 L4+missing", inp(findings=[F(auth="missing")]),
        6, "REVIEW", "DP3")
    r7 = chk("A07 链7 L4+ok", inp(findings=[F(auth="ok")]), 7, "BLOCK", "DP2")
    chk("A08 链8 L3+missing", inp(findings=[F(sev="L3", auth="expired")]),
        8, "REVIEW", "DP3")
    chk("A09 链9 L3+ok", inp(findings=[F(sev="L3", auth="ok")]),
        9, "REVIEW", "DP3")
    chk("A10 链10 L2+missing", inp(findings=[F(sev="L2", auth="missing")]),
        10, "REVIEW", "DP3")
    chk("A11 链11 partial", inp(coverage_state="partial", findings=[]),
        11, "REVIEW", "DP3")
    chk("A12 链12 parse partial", inp(parse_status="partial", findings=[]),
        12, "REVIEW", "DP3")
    chk("A13 链13 candidate", inp(findings=[F("c", status="candidate", sev="L5", auth=None)]),
        13, "REVIEW", "DP3")
    chk("A14 链14 L2+ok", inp(findings=[F(sev="L2", auth="ok")]),
        14, "待自决", "DP1")
    chk("A15 链15 PASS", inp(findings=[]), 15, "PASS", "DP1")

    # ── B 顺序即裁决 ────────────────────────────────────────────────
    T("B1 coverage missing 先于 L4 BLOCK",
      decide(inp(coverage_state="missing", findings=[F(sev="L4", auth="ok")]))["state"] == "未审查", "")
    T("B2 parse failed 先于 rule_conflict",
      decide(inp(parse_status="failed", failure_kind="empty", rule_conflict=True))["state"] == "未审查", "")
    T("B3 rule_conflict 先于 L4 BLOCK",
      decide(inp(findings=[F(sev="L4", auth="ok")], rule_conflict=True))["state"] == "REVIEW", "")
    T("B4 any authority conflict 先于 L4 BLOCK",
      decide(inp(findings=[F(sev="L4", auth="conflict"), F("x", sev="L2", auth="ok")]))["state"] == "REVIEW", "")
    T("B5 L4 BLOCK 先于 partial",
      decide(inp(coverage_state="partial", findings=[F(sev="L4", auth="ok")]))["state"] == "BLOCK", "")
    r_b5 = decide(inp(coverage_state="partial", findings=[F(sev="L4", auth="ok")]))
    T("B5b BLOCK+partial 挂 partial_coverage", "partial_coverage" in r_b5.get("obligations", []),
      str(r_b5.get("obligations")))
    T("B6 partial 先于 PASS",
      decide(inp(coverage_state="partial"))["state"] != "PASS", "")
    T("B7 L4 先于 candidate/partial/待自决",
      decide(inp(parse_status="partial", coverage_state="partial",
                 findings=[F(sev="L4", auth="ok"), F("c", status="candidate", sev="L5", auth=None)]))["state"] == "BLOCK", "")

    # ── C candidate / L0 / partial ─────────────────────────────────
    r_c = decide(inp(findings=[F("c", status="candidate", sev="L5", auth=None)]))
    T("C1 candidate L5 单独 → REVIEW 而非 BLOCK", r_c["state"] == "REVIEW", str(r_c["state"]))
    T("C2 candidate 不贡献 max_sev（max_sev=none）", r_c.get("max_sev") == "none", str(r_c.get("max_sev")))
    r_p = decide(inp(coverage_state="partial"))
    T("C3 partial 干净 → REVIEW 且 coverage_incomplete=true",
      r_p["state"] == "REVIEW" and r_p.get("coverage_incomplete") is True, str(r_p))
    r_l0 = decide(inp(findings=[F(sev="L0", auth="ok")]))
    T("C4 L0 confirmed → ERROR(I4)",
      r_l0["run_state"] == "ERROR" and r_l0.get("invariant_violation") == "I4"
      and r_l0.get("state") is None and r_l0.get("external_label") is None, str(r_l0))

    # ── D I1–I7 ─────────────────────────────────────────────────────
    inv_cases = [
        ("I1", inp(parse_status="ok", failure_kind="empty")),
        ("I2", inp(parse_status="failed", failure_kind=None)),
        ("I3", inp(findings=[], max_sev="none", max_sev_authority="ok")),
        ("I4", inp(findings=[F(sev="L0", auth="ok")])),
        ("I5", inp(parse_status="failed", failure_kind="empty",
                   findings=[F(sev="L2", auth="ok")])),
        ("I6", inp(findings=[F(sev="L4", auth="ok")], max_sev="L4",
                   max_sev_authority="conflict", any_authority_conflict=False)),
        ("I7", inp(findings=[], max_sev="none", max_sev_authority="n/a",
                   any_authority_conflict=True)),
    ]
    for code, x in inv_cases:
        r = decide(x)
        T("D%s %s → ERROR、both null、obligation 记录" % (code, code),
          r.get("run_state") == "ERROR" and r.get("invariant_violation") == code
          and r.get("state") is None and r.get("external_label") is None
          and "invariant_violation" in (r.get("obligations") or []), str(r))

    # ── E 并行义务 ──────────────────────────────────────────────────
    r_e1 = decide(inp(findings=[F(sev="L4", auth="ok"),
                                F("c", status="candidate", sev="L5", auth=None)]))
    T("E1 BLOCK+candidate → pending_candidate",
      r_e1["state"] == "BLOCK" and "pending_candidate" in r_e1["obligations"], str(r_e1["obligations"]))
    r_e2 = decide(inp(findings=[F(sev="L4", auth="ok"),
                                F("g", sev="L2", auth="missing")]))
    T("E2 confirmed 依据缺失 → evidence_gap",
      "evidence_gap" in r_e2["obligations"], str(r_e2["obligations"]))
    r_e3 = decide(inp())
    T("E3 无义务 → obligations 是空数组（字段不省略）",
      r_e3.get("obligations") == [], str(r_e3.get("obligations")))
    T("E4 并行义务不重复",
      len(r_b5["obligations"]) == len(set(r_b5["obligations"])), str(r_b5["obligations"]))

    # ── F 输出契约 ──────────────────────────────────────────────────
    seen = set()
    for x in [inp(findings=[F(sev="L4", auth="ok")]),
              inp(findings=[F(sev="L3", auth="ok")]),
              inp(coverage_state="missing"),
              inp(findings=[F(sev="L2", auth="ok")]),
              inp()]:
        r = decide(x)
        seen.add(r["state"])
        T("F1 %s 的 release_status=待放行" % r["state"],
          r.get("release_status") == "待放行", str(r.get("release_status")))
        T("F1b %s 有 external_label 且等于 state" % r["state"],
          r.get("external_label") == r.get("state"), str(r.get("external_label")))
    T("F2 五标签都可达", seen == FIVE_STATES, str(sorted(seen)))
    r_err = decide(inp(findings=[F(sev="L0", auth="ok")]))
    T("F3 ERROR 的 release_status 不是标签值",
      r_err.get("release_status") not in FIVE_STATES, str(r_err.get("release_status")))

    # ── G 唯一实现：不许 import 第二个判定实现 ──────────────────────
    src = open(os.path.join(ROOT, "base", "decision_table.py"), encoding="utf-8").read()
    imports = re.findall(r"^\s*(?:from|import)\s+([A-Za-z0-9_\.]+)", src, re.M)
    forbidden = {"judge_adapter", "status_resolver", "decision_table_v2",
                 "decision_table_legacy", "judge_chain", "disposition_routing"}
    T("G1 不 import 第二个判定实现", not (set(imports) & forbidden), str(sorted(set(imports))))
    T("G2 只 import 标准库（不 import 仓内其他判定模块）",
      all(m.split(".")[0] in {"__future__", "typing", "json", "re", "hashlib"} for m in imports),
      str(sorted(set(imports))))

    # ── H 输入读不出 / 派生值不一致 → ERROR，不得默认 PASS/BLOCK ────
    bad_inputs = [
        None, [], {}, {"parse_status": "bogus", "coverage_state": "full", "findings": []},
        {"parse_status": "ok", "coverage_state": "bogus", "findings": []},
        {"parse_status": "ok", "coverage_state": "full", "findings": "x"},
        {"parse_status": "ok", "coverage_state": "full",
         "findings": [{"status": "confirmed", "severity": "L9", "authority_state": "ok"}]},
        {"parse_status": "ok", "coverage_state": "full",
         "findings": [{"status": "confirmed", "severity": "L2"}]},
    ]
    for i, x in enumerate(bad_inputs):
        r = decide(x)
        T("H1 坏输入 #%d → ERROR 且 state=null" % i,
          isinstance(r, dict) and r.get("run_state") == "ERROR" and r.get("state") is None,
          str(r))
    r_mis = decide(inp(findings=[F(sev="L4", auth="ok")], max_sev="L1"))
    T("H2 声明 max_sev 与 findings 不一致 → ERROR（不许按假数据判）",
      r_mis.get("run_state") == "ERROR", str(r_mis))

    # 确定性
    T("H3 同一输入连跑两次结果一致",
      decide(inp(findings=[F(sev="L4", auth="ok")])) == decide(inp(findings=[F(sev="L4", auth="ok")])), "")

    # ── J 判定逻辑唯一性：全仓静态扫描（C-46 / L2-1a） ──────────────
    scanned, hits = scan_decision_logic()
    T("J0 扫描范围非空（不是空集恒真）", len(scanned) > 0, "scanned=%d" % len(scanned))
    unwhitelisted = {p: h for p, h in hits.items() if p not in SCAN_WHITELIST}
    T("J1 除白名单外没有任何模块写状态/层/对外标签",
      unwhitelisted == {}, str({p: h[:3] for p, h in unwhitelisted.items()}))
    T("J2 白名单条目都必须有非空理由",
      all(isinstance(r, str) and r.strip() for r in SCAN_WHITELIST.values()),
      str({p: repr(r) for p, r in SCAN_WHITELIST.items()}))
    T("J3 白名单路径都存在", all(os.path.exists(os.path.join(ROOT, p)) for p in SCAN_WHITELIST),
      str([p for p in SCAN_WHITELIST if not os.path.exists(os.path.join(ROOT, p))]))
    stale = [p for p in SCAN_WHITELIST if p not in hits]
    T("J4 白名单不许过期（登记了却已无命中）", stale == [], str(stale))
    # 反向对照：临时副本塞一段 if/else 标签计算 → 必须命中；删掉 → 不命中
    api_rel = "api/review_api.py"
    api_path = os.path.join(ROOT, api_rel)
    original = open(api_path, encoding="utf-8").read()
    tmp = tempfile.mkdtemp(prefix="decision-scan-")
    try:
        rogue = original + '\nstate = "BLOCK" if True else "REVIEW"\n'
        rogue_path = os.path.join(tmp, "review_api.py")
        with open(rogue_path, "w", encoding="utf-8") as f:
            f.write(rogue)
        T("J5 临时副本塞入 state=BLOCK if ... → 扫描必须命中",
          decision_writes_in_file(rogue_path) != [], str(decision_writes_in_file(rogue_path)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    T("J6 原文件删掉变异后不命中（反向对照不是恒红）",
      decision_writes_in_file(api_path) == [], str(decision_writes_in_file(api_path)))
    T("J7 只读字段不误报（item.get(\"state\")）",
      decision_writes_in_text('value = item.get("state")\n') == [], "")

    for f in fails:
        print("  ❌ " + f)
    verdict = "❌" if fails else "✅"
    print("\n%s verify_decision_table %d 项检查 · %d 项红" % (verdict, checks, len(fails)))
    print("  扫描 %d 个 .py · 命中 %d 个文件 · 白名单 %d 条"
          % (len(scanned), len(hits), len(SCAN_WHITELIST)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
