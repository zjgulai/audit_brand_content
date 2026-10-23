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
    H3 改为与独立期望表对拍（不再 `decide(x) == decide(x)` 自比），
    并用「三个不同输入必须给出不同标签」保证常量实现必红。
  L **两套刻度互不推导**（验收行 18）：finding_store 的 P/L 两张枚举表
    （域内接受 / 域外 P4·P5·「高危」·L6 拒收）；生产 `_SEV_RANK` 恰为 L0..L5
    且 rank(L0) < rank(L1)（排序不许把 L0 当最小值）；源码里没有 P 值参与
    min/max/sorted/比较；severity 域外值在判定入口同样被拒。
  M **输入域与派生量**（验收行 30）：parse_status/failure_kind 域外值 →
    ERROR 且明细点名 bad_*（不许被链末兜底掩盖）；gaps 与独立期望逐位相等、
    顺序跟随输入、candidate/rejected 不计入；同级 conflict 与 expired 同现取
    conflict（_AUTH_RANK 的行为对拍）。
  N **数量不降级 / 兜底封闭 / ERROR 契约**（验收行 28/38/27/47）：
    confirmed 1→3→10→100 条状态严重度不下降、最严重的排在第 100 位也不许被
    截掉；判定表保底出口文本级钉死为 `else: return _error("NO_CHAIN",…)`
    且恰一处、不存在 pass_flag 一类 PASS 使能开关；全合法输入域穷举
    （排除 I1/I2/I4 非法组合）无一格落兜底且 15 链全覆盖；ERROR 出口
    layer/release_status 也为 null；candidate+L0 正常出结论（I4 只对 confirmed）。
  O **渲染侧标签封闭**（验收行 47 ④）：report_render.mjs 的 LABELS 词表
    静态恰为五标签、定义恰一处；真实渲染器对 BLOCK 好样本完整渲出、
    对 state=ERROR / state=null 的 IR 一律拦下（ok=false / md=null / text=null）。
  P **candidate 与 L0**（验收行 31 反向对照）：candidate+L0 必须正常出
    结论（链 13 REVIEW），I4 只对 confirmed。

## --controls

  `--controls` 只跑上面新增断言的反向对照（好样本必须绿、坏样本必须红、
  结构钉的好副本必须可编译）——断言自己也要被验证（没红过的断言不算验证过它）。

## 退出码

  0 全过 · 1 有红 · 2 未测（node 不可用 —— O 段 renderer 断言测不了，不许当绿）
"""
from __future__ import annotations

import ast
import itertools
import json
import os
import re
import shutil
import subprocess
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
FIVE_LABELS_TEXT = '["BLOCK", "REVIEW", "未审查", "待自决", "PASS"]'
LAYERS = {"DP0", "DP1", "DP2", "DP3", "DP4"}
UNKNOWN_AXES = ("family", "scene_domain", "authority_source", "consequence")

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


# ── L/M/N/O 段的构件 ────────────────────────────────────────────────────
# ★ 这些构件同时被主检查与 --controls 使用：--controls 喂坏样本时调的就是
#   主检查跑的同一份函数 —— 断言与它的反向对照不许各养一份实现（§2.4.1）。

# L 段（行 18）：finding_store 的两张枚举表，原样从生产文件抄在这里。
# 生产改动（收窄/扩域）会让「与这里的独立副本恒等」变红。
EXPECTED_DETECTED_BY = {"P0", "P1", "P2", "P3"}
EXPECTED_SEVERITY = {"L0", "L1", "L2", "L3", "L4", "L5"}


def finding_store_enums():
    """直接 import 生产 finding_store，取两张枚举 frozenset。"""
    ns = {"__name__": "finding_store_probe"}
    with open(os.path.join(ROOT, "base", "finding_store.py"), encoding="utf-8") as f:
        code = f.read()
    exec(compile(code, "finding_store.py", "exec"), ns)
    return ns["VALID_DETECTED_BY"], ns["VALID_SEVERITY"]


def finding_store_check(rec):
    """跑生产 check_record，返回 FindingRejected 的 detail 或 None（接受）。"""
    ns = {"__name__": "finding_store_probe"}
    with open(os.path.join(ROOT, "base", "finding_store.py"), encoding="utf-8") as f:
        code = f.read()
    exec(compile(code, "finding_store.py", "exec"), ns)
    try:
        ns["check_record"](rec)
        return None
    except Exception as e:  # noqa: BLE001
        return str(e)


def _fs_record(**over):
    rec = {
        "finding_id": "f-l", "control_code": "H01", "detected_by": "P0",
        "authority_ref": [], "authority_state": "ok", "severity": "L4",
        "status": "confirmed", "location": {"kind": "text_span",
                                            "start": 0, "end": 1},
        "quote": "q", "produced_by": "rule", "derived_from": None,
    }
    rec.update(over)
    return rec


_P_SEVERITY_PROBE = re.compile(
    r'\b(?:min|max|sorted|sort)\s*\([^)]*\b(?:P[0-5]|detected_by)\b[^)]*\)')


def _p_scale_comparisons(dt_src):
    """severity 表达式里出现 P 值 / P 值参与 min·max·sorted —— 两套刻度互推导。"""
    hits = []
    for i, line in enumerate(dt_src.splitlines(), 1):
        code = line.split("#")[0]
        if "P" not in code and "detected_by" not in code:
            continue
        if re.search(r'"severity"\s*,\s*"P|severity.*\bP[0-5]\b', code) \
                or _P_SEVERITY_PROBE.search(code):
            hits.append((i, line.strip()))
    return hits


NO_CHAIN_SNIPPET = 'return _error("NO_CHAIN", "no chain matched", derived)'
NO_CHAIN_GUARD_RE = re.compile(
    r"else:\s*\n[^\S\n]*#[^\n]*\n[^\S\n]*" + re.escape(NO_CHAIN_SNIPPET))
PASS_FLAG_RE = re.compile(
    r"^\s*(\w+)\s*=\s*(?:False|True)\s*(?:#.*)?$")
CHAIN_TOKEN_RE = re.compile(
    r"chain,\s*state,\s*layer\s*=\s*(\d+)\s*,\s*([^,]+),\s*([^\s]+)")
NO_CHAIN_LABELS = {"PASS", "BLOCK", "REVIEW", "待自决"}


def _dt_text():
    with open(os.path.join(ROOT, "base", "decision_table.py"), encoding="utf-8") as f:
        return f.read()


def no_chain_pins(dt_src):
    """行 27/38 的结构钉：保底出口必须存在、恰一处、且真的抛 ERROR 不给标签。

    返回 (problems, pass_flags)：
      problems    结构钉失败的明细（空 = 钉住了）
      pass_flags  模块级 `xxx = False/True` 布尔旗的 (名字, 行) 清单 ——
                  PASS 使能开关探针；任何新旗都必须在 PASS 使能白名单里
                  （否则「加一面旗把兜底放行成 PASS」从静态上就被拦下）。
    """
    problems = []
    n = dt_src.count(NO_CHAIN_SNIPPET)
    if n == 0:
        problems.append("no_chain_absent")
    elif n != 1:
        problems.append("no_chain_count:%d" % n)
    if not NO_CHAIN_GUARD_RE.search(dt_src):
        problems.append("no_chain_not_in_else_guard")
    flags = []
    for i, line in enumerate(dt_src.splitlines(), 1):
        m = PASS_FLAG_RE.match(line)
        if m and not line.lstrip().startswith("#"):
            flags.append((m.group(1), i))
    return problems, flags


def _legal_findings():
    """行 27/38 穷举用的合法单 finding 域：排除 I1/I2/I4 非法组合。"""
    out = [None]
    for st in ("confirmed", "candidate", "rejected", "superseded"):
        for sev in ("L1", "L2", "L3", "L4", "L5"):
            if st != "confirmed":
                out.append({"status": st, "severity": sev})
                continue
            for auth in ("ok", "missing", "expired", "conflict"):
                out.append({"status": st, "severity": sev, "authority_state": auth})
    return out


def exhaustive_no_chain_scan():
    """穷举合法输入域：返回 (checked, no_chain 组合, chains 命中集合)。"""
    checked = 0
    no_chain = []
    chains = set()
    for ps, fk, cov, rc, f in itertools.product(
            ("ok", "partial", "failed"),
            (None, "fetch_error", "parse_error", "empty", "unsupported"),
            ("missing", "partial", "full"),
            (False, True),
            _legal_findings()):
        # I1: parse≠failed 时 failure_kind 必须为 None；I2: failed 必须有
        # failure_kind —— 这两类是非法输入（I1/I2 违反样本，不在穷举域内）。
        if ps != "failed" and fk is not None:
            continue
        if ps == "failed" and fk is None:
            continue
        # I5: failed 不许带 findings（违反样本）。
        if ps == "failed" and f is not None:
            continue
        # 不给 authority_state 的 confirmed 是缺派生输入（判据的输入 schema
        # 要求 confirmed 带 authority_state）；候选/驳回/取代不限。
        if f is not None and f["status"] == "confirmed" \
                and "authority_state" not in f:
            continue
        x = {"parse_status": ps, "failure_kind": fk, "coverage_state": cov,
             "rule_conflict": rc}
        x["findings"] = [] if f is None else [dict(
            f, finding_id="e", control_code="H01", rule_conflict=False,
            quote="q", produced_by="rule", detected_by="P0")]
        r = decide(x)
        checked += 1
        if r.get("run_state") == "OK":
            chains.add(r.get("chain"))
        elif "no chain" in str(r.get("error_reason")):
            no_chain.append((ps, fk, cov, rc, (f or {}).get("status")))
    return checked, no_chain, chains


def _f(fid="f1", status="confirmed", sev="L4", auth="ok"):
    return {"finding_id": fid, "control_code": "H01", "status": status,
            "severity": sev, "authority_state": auth, "rule_conflict": False,
            "quote": "q", "produced_by": "rule", "detected_by": "P0"}


def _gap_ids(x):
    return [g if isinstance(g, str) else g.get("finding_id")
            for g in (decide(x).get("all_evidence_gaps") or [])]


# ── O 段（行 47 ④）：真实渲染器 ─────────────────────────────────────────

def _node_available():
    return shutil.which("node") is not None


def _render_snapshot(decision, ir_id="ir-c47"):
    """O 段探针快照。

    ★ 除了 `decision.state` 之外的一切字段都给**合法值**（release_status 必须是
      「待放行」而不是 None！）—— 让基线里拦下它的**只能是**「state 不在
      五标签」这一道门。否则（比如 release_status=None）渲染器会先被别的
      校验拦下，探针变成**恒红**，LABELS 词表被改坏也测不出来。
    """
    return {
        "ir": {"ir_id": ir_id, "ir_version": "review-ir-v1",
               "source_ir_version": "cu-c47",
               "findings": [],
               "decision": decision,
               "coverage": {"coverage_state": "full"}},
        "failure_kind_counts": {"fetch_error": 0, "parse_error": 0,
                                "empty": 0, "unsupported": 0},
        "unknown_bucket_counts": {},
        "evidence": [], "unassessed": [],
        "receipt": {"skill": "s", "version": "1", "fingerprint": "f" * 64,
                    "skipped_steps": "无", "rule_snapshot": "rs-c47"},
        "report_url": "https://static.example.com/reports/c47.md",
    }


def _render_via_node(snapshots):
    """跑真实渲染器：返回 [(ok, md_null, text_null)]，与输入一一对应。"""
    tmp = tempfile.mkdtemp(prefix="decision-render-")
    mod = "file://" + os.path.join(ROOT, "tools", "audit", "report_render.mjs")
    runner = os.path.join(tmp, "render.mjs")
    with open(runner, "w", encoding="utf-8") as f:
        f.write(
            "import { renderReport, renderMessage } from %r;\n"
            "let input='';\n"
            "for await (const c of process.stdin) input += c;\n"
            "const list = JSON.parse(input);\n"
            "const out = list.map((snap) => {\n"
            "  const rep = renderReport(snap), msg = renderMessage(snap);\n"
            "  return {ok: rep.ok && msg.ok, mdNull: rep.markdown === null,\n"
            "          textNull: msg.text === null};\n"
            "});\n"
            "process.stdout.write(JSON.stringify(out));\n" % mod)
    p = subprocess.run(["node", runner], cwd=ROOT,
                       input=json.dumps(snapshots, ensure_ascii=False),
                       text=True, capture_output=True, timeout=120)
    shutil.rmtree(tmp, ignore_errors=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[-400:])
    return [(o.get("ok"), o.get("mdNull"), o.get("textNull"))
            for o in json.loads(p.stdout)]


# N2 的 PASS 使能白名单：`base/decision_table.py` 里现存的全部模块级布尔旗。
# 出现旗名单之外的新旗 → 静态红（防「加一面旗把兜底放行成 PASS」）；
# 白名单里的旗若被改指向 PASS 使能 → N1 的结构钉与行为级穷举兜住。
PASS_FLAG_ALLOW = {"__future___annotations"}


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

    # ── L 两套刻度互不推导（验收行 18）──────────────────────────────
    # 前一轮变异实测：detected_by 枚举（finding_store）与「L0 排序不当」
    # 各 survived 一条 —— 本段把两边都钉住。
    try:
        p_enum, s_enum = finding_store_enums()
        fs_err = None
    except Exception as e:  # noqa: BLE001
        p_enum = s_enum = None
        fs_err = str(e)
    T("L1 finding_store 的 detected_by 枚举恰为 {P0..P3}（与验证器独立副本恒等）",
      fs_err is None and p_enum == EXPECTED_DETECTED_BY, str(p_enum or fs_err))
    T("L2 finding_store 的 severity 枚举恰为 {L0..L5}（与验证器独立副本恒等）",
      fs_err is None and s_enum == EXPECTED_SEVERITY, str(s_enum or fs_err))
    if fs_err is None:
        T("L3 detected_by 域内 P2 被接受（不是把整张表写成摆设）",
          finding_store_check(_fs_record(detected_by="P2")) is None,
          str(finding_store_check(_fs_record(detected_by="P2"))))
        T("L4 detected_by 域外 P4 被拒",
          finding_store_check(_fs_record(detected_by="P4")) is not None,
          str(finding_store_check(_fs_record(detected_by="P4"))))
        T("L5 detected_by 域外「高危」被拒（中文严重度词不许混进检测层）",
          finding_store_check(_fs_record(detected_by="高危")) is not None,
          str(finding_store_check(_fs_record(detected_by="高危"))))
        T("L6 severity 域外 L6 被拒",
          finding_store_check(_fs_record(severity="L6")) is not None,
          str(finding_store_check(_fs_record(severity="L6"))))
    else:
        T("L3 finding_store 读不出（%s）—— 域内/域外行为全未测" % fs_err, False, "")
    # 排序半边：`_SEV_RANK` 恰为 L0..L5、rank 递增、L0 不是最小值。
    dt_src_main = _dt_text()
    m_rank = re.search(r"_SEV_RANK\s*=\s*(\{[^\n]*\})", dt_src_main)
    T("L7 生产 _SEV_RANK 表存在", m_rank is not None, "未找到 _SEV_RANK")
    if m_rank:
        try:
            rank = ast.literal_eval(m_rank.group(1))
        except (ValueError, SyntaxError):
            rank = None
        want_rank = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4, "L5": 5}
        T("L8 _SEV_RANK 恰为 L0..L5 且 rank 严格递增（L0 不是最小值）",
          rank == want_rank, repr(rank))
    T("L9 severity 表达式里没有 P 值参与、P 值不进 min/max/sorted",
      _p_scale_comparisons(dt_src_main) == [],
      str(_p_scale_comparisons(dt_src_main)[:3]))
    T("L10 判定入口对 severity 域外值也拒（两套刻度同一堵墙）",
      decide(inp(findings=[F(sev="L6", auth="ok")]))["run_state"] == "ERROR",
      str(decide(inp(findings=[F(sev="L6", auth="ok")]))))
    # 行为半边：把 L0 confirmed 换成 L1 结论必须下降（排序真的按 rank 走）。
    r_l0_as = decide(inp(findings=[F(sev="L0", auth="ok"),
                                   F("b", sev="L1", auth="ok")]))
    r_l1_as = decide(inp(findings=[F(sev="L1", auth="ok")]))
    T("L11 把 L0 改成 L1 结论必须下降（I4 → 待自决；排序按 rank 不按位置）",
      r_l0_as["run_state"] == "ERROR" and r_l1_as["state"] == "待自决",
      "L0:%r L1:%r" % (r_l0_as.get("run_state"), r_l1_as.get("state")))

    # ── M 输入域与派生量（验收行 30）────────────────────────────────
    r_badps = decide(inp(parse_status="unknown"))
    T("M1 parse_status=unknown → ERROR 且明细点名 bad_parse_status（不许被兜底掩盖）",
      r_badps["run_state"] == "ERROR"
      and "bad_parse_status" in str(r_badps.get("error_reason")), str(r_badps))
    r_badfk = decide(inp(parse_status="ok", failure_kind="nonsense"))
    T("M2 failure_kind=nonsense → ERROR 且明细点名 bad_failure_kind",
      r_badfk["run_state"] == "ERROR"
      and "bad_failure_kind" in str(r_badfk.get("error_reason")), str(r_badfk))
    r_covmap = decide(inp(coverage_state="partial", findings=[]))
    T("M3 coverage missing/partial/full 映射不变（missing→未审查、partial→REVIEW）",
      decide(inp(coverage_state="missing"))["state"] == "未审查"
      and r_covmap["state"] == "REVIEW",
      "%r/%r" % (decide(inp(coverage_state="missing"))["state"], r_covmap["state"]))
    gaps_want = ["g1", "g2", "g4", "g5", "g6", "g7", "g8", "g9", "g10"]
    gaps_x = inp(findings=[
        _f("g1", auth="missing"), _f("g2", auth="expired"),
        _f("g3", auth="ok"), _f("g4", sev="L2", auth="missing"),
        _f("g5", sev="L2", auth="expired"), _f("g6", sev="L3", auth="missing"),
        _f("g7", sev="L3", auth="expired"), _f("g8", sev="L4", auth="missing"),
        _f("g9", sev="L5", auth="expired"), _f("g10", sev="L5", auth="missing"),
        _f("g11", status="candidate", sev="L5", auth=None),
        _f("g12", status="rejected", sev="L4", auth="missing"),
        _f("g13", status="superseded", sev="L5", auth="missing"),
    ])
    T("M4 gaps 恰为那 9 条 confirmed 依据缺失的 id（含全部 L 档）、"
      "顺序跟随输入、candidate/rejected/superseded 不计入",
      _gap_ids(gaps_x) == gaps_want, repr(_gap_ids(gaps_x)))
    T("M5 gaps 单条样本：id 来自 finding_id、candidate 不计入",
      _gap_ids(inp(findings=[_f("only", auth="missing"),
                             _f("cand", status="candidate", auth="missing")]))
      == ["only"], repr(_gap_ids(inp(findings=[_f("only", auth="missing")]))))
    r_ord = decide(inp(findings=[_f("o1", auth="expired"), _f("o2", auth="conflict")]))
    T("M6 同级 conflict 与 expired 同现 → 取 conflict（_AUTH_RANK 行为对拍）",
      r_ord.get("max_sev_authority") == "conflict", str(r_ord.get("max_sev_authority")))
    r_ord2 = decide(inp(findings=[_f("o1", auth="ok"), _f("o2", auth="conflict")]))
    T("M7 ok 与 conflict 同现 → conflict（rank 表真的被用）",
      r_ord2.get("max_sev_authority") == "conflict", str(r_ord2.get("max_sev_authority")))

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

    # H3 不再拿 decide 和自己比（旧版 `decide(x) == decide(x)` 对常量实现恒真）。
    # 改为与**独立期望表**逐项对拍；再用「不同输入必须给出不同标签」证明
    # 常量/退化实现必红。
    expected_rows = [
        ("H3a chain7", inp(findings=[F(sev="L4", auth="ok")]),
         7, "BLOCK", "DP2"),
        ("H3b chain15", inp(), 15, "PASS", "DP1"),
        ("H3c chain1", inp(coverage_state="missing"), 1, "未审查", "DP0"),
    ]
    got_rows = []
    for cid, x, chain, state, layer in expected_rows:
        r = decide(x)
        got_rows.append(r)
        T("%s 与独立期望表对拍" % cid,
          r.get("chain") == chain and r.get("state") == state
          and r.get("layer") == layer and r.get("external_label") == state
          and r.get("release_status") == "待放行",
          "want chain=%r state=%r layer=%r got=%r"
          % (chain, state, layer, {k: r.get(k) for k in
                                   ("chain", "state", "layer",
                                    "external_label", "release_status")}))
    T("H3d ★ 常量实现必红：三个不同输入不得返回同一组标签",
      len({(r.get("chain"), r.get("state"), r.get("layer"))
           for r in got_rows}) == len(expected_rows),
      repr([(r.get("chain"), r.get("state"), r.get("layer"))
            for r in got_rows]))
    T("H3e ★ 输出必须带 chain 字段（契约漏项探针）",
      all(r.get("chain") is not None for r in got_rows),
      repr([r.get("chain") for r in got_rows]))

    # ── K 未知桶（Playbook §5.3.3 / 验收行 77）──────────────────────
    unknown_cases = [
        ("family", "未归类", "DP3"),
        ("scene_domain", "其他", "DP3"),
        ("authority_source", "依据待定", "DP4"),
        ("consequence", "后果未知", "DP4"),
    ]
    for axis, value, layer in unknown_cases:
        r = decide(inp(**{axis: value}))
        T("K1 %s=未知桶 → REVIEW/%s + 计数 + 转人原因" % (axis, layer),
          r.get("state") == "REVIEW" and r.get("layer") == layer
          and r.get("chain") == 16
          and r.get("handoff_reason") == "unknown_bucket"
          and r.get("target_layer") == layer
          and r.get("unknown_buckets", {}).get(axis) == 1
          and r.get("unknown_bucket_total") == 1
          and ("unknown_bucket:%s" % axis) in (r.get("obligations") or []),
          str(r))
    r_known = decide(inp(family="宣称控制", scene_domain="车内",
                         authority_source="external", consequence="低"))
    T("K2 已知值不得误转人工",
      r_known.get("state") == "PASS" and r_known.get("layer") == "DP1"
      and r_known.get("unknown_bucket_total") == 0
      and r_known.get("handoff_reason") is None, str(r_known))
    r_zero = decide(inp())
    T("K3 全为 0 时四个计数仍出现",
      set(r_zero.get("unknown_buckets") or {}) == set(UNKNOWN_AXES)
      and all(r_zero["unknown_buckets"][a] == 0 for a in UNKNOWN_AXES)
      and r_zero.get("unknown_bucket_total") == 0, str(r_zero.get("unknown_buckets")))
    r_batch = decide(inp(family="未归类", scene_domain="其他",
                         authority_source="依据待定", consequence="后果未知"))
    T("K4 四类同批 → 各计 1、总数 4、DP4",
      r_batch.get("unknown_bucket_total") == 4
      and all(r_batch["unknown_buckets"][a] == 1 for a in UNKNOWN_AXES)
      and r_batch.get("layer") == "DP4", str(r_batch.get("unknown_buckets")))
    f_unknown = F(sev="L2", auth="ok")
    f_unknown["family"] = "未归类"
    r_finding = decide(inp(findings=[f_unknown]))
    T("K5 finding 上的未知桶同样生效",
      r_finding.get("state") == "REVIEW" and r_finding.get("layer") == "DP3"
      and r_finding.get("unknown_buckets", {}).get("family") == 1, str(r_finding))
    r_block = decide(inp(findings=[F(sev="L4", auth="ok")], family="未归类"))
    T("K6 ★ BLOCK + 未知桶 → 仍必须 BLOCK（不得降级）",
      r_block.get("state") == "BLOCK" and r_block.get("layer") == "DP2"
      and r_block.get("chain") == 7 and r_block.get("unknown_bucket_total") == 1
      and r_block.get("handoff_reason") is None, str(r_block))
    r_cov_missing = decide(inp(coverage_state="missing", family="未归类"))
    T("K7 coverage missing 优先于未知桶 → 未审查/DP0",
      r_cov_missing.get("state") == "未审查"
      and r_cov_missing.get("layer") == "DP0"
      and r_cov_missing.get("unknown_bucket_total") == 1, str(r_cov_missing))
    r_parse_failed = decide(inp(parse_status="failed", failure_kind="empty",
                                family="未归类"))
    T("K8 parse failed 优先于未知桶 → 未审查/DP0",
      r_parse_failed.get("state") == "未审查"
      and r_parse_failed.get("layer") == "DP0"
      and r_parse_failed.get("unknown_bucket_total") == 1, str(r_parse_failed))

    # ── N 兜底封闭 / 数量不降级 / ERROR 契约（验收行 27/38/28/47）──
    dt_src = _dt_text()
    pin_problems, pass_flags = no_chain_pins(dt_src)
    T("N1 ★ 保底出口结构钉：`else: return _error(\"NO_CHAIN\", …)` 恰一处"
      "且真抛 ERROR（行 27/38：改兜底或整段删掉必须当场红）",
      pin_problems == [], str(pin_problems))
    T("N2 ★ 不存在 PASS 使能开关（新模块级布尔旗必须登记进白名单）",
      all(name in PASS_FLAG_ALLOW for name, _ in pass_flags),
      str([n for n, _ in pass_flags if n not in PASS_FLAG_ALLOW]))
    n_checked, n_no_chain, n_chains = exhaustive_no_chain_scan()
    T("N3 穷举样本数非零（穷举不许是空集恒真）", n_checked >= 200,
      "checked=%d" % n_checked)
    T("N4 ★ 全合法输入域无一格落 NO_CHAIN 兜底、漏写数为 0",
      n_no_chain == [], str(n_no_chain[:5]))
    T("N5 链号全部 ∈1-15（无「未定义」分支、无第 16 条链号）",
      all(isinstance(c, int) and 1 <= c <= 15 for c in n_chains)
      and len(n_chains) == 15, "chains=%r" % sorted(n_chains))
    # 行 28：数量不降级 + 呈现数量分离。★ 最严重的 L4 刻意放在第 3 位与
    # 第 100 位、其余全部 L1 —— 「第 3 条起全部截掉」的变异必须在这里红，
    # 不能指望 gaps 那侧的断言顺带兜住。
    many = [F("m%d" % i, sev="L1", auth="ok") for i in range(1, 101)]
    many[2] = F("m3", sev="L4", auth="ok")     # 最严重的在第 3 位
    many[99] = F("m100", sev="L4", auth="ok")  # 最严重的在第 100 位
    r3 = decide(inp(findings=many[:3]))
    r10 = decide(inp(findings=many[:10]))
    r100 = decide(inp(findings=many))
    T("N6 ★ 数量不降级：confirmed 1→3→10→100 条（最严重排第 3 与第 100 位）"
      "结论不许从 BLOCK 掉下来（「第 3 条起截掉」必须当场红）",
      r3["state"] == r10["state"] == r100["state"] == "BLOCK"
      and r3["chain"] == r10["chain"] == r100["chain"] == 7,
      "1→3:%r/10:%r/100:%r" % (r3["state"], r10["state"], r100["state"]))
    T("N7 呈现数量分离：状态同档时输入条数不并入结论档（决定档位的只有 severity）",
      len({r3["chain"], r10["chain"], r100["chain"]}) == 1
      and len(many) == 100, "chains=%r" % ([r3["chain"], r10["chain"]],))
    r_err47 = decide(inp(findings=[F(sev="L0", auth="ok")]))
    T("N8 ★ ERROR 出口 layer 与 release_status 也必须为 null（行 47："
      "不只 state/external_label）",
      r_err47.get("layer") is None and r_err47.get("release_status") is None,
      "layer=%r release=%r" % (r_err47.get("layer"), r_err47.get("release_status")))

    # ── O 渲染侧标签封闭（验收行 47 ④）────────────────────────────
    if not _node_available():
        T("O0 node 不可用 —— 渲染侧断言未测（不许当绿）", False, "⚠ 未测")
    else:
        try:
            rendered = _render_via_node([
                _render_snapshot({"state": "BLOCK", "layer": "DP2",
                                  "release_status": "待放行", "obligations": []}),
                _render_snapshot({"state": "ERROR", "layer": None,
                                  "release_status": "待放行", "obligations": []}),
                _render_snapshot({"state": None, "layer": None,
                                  "release_status": "待放行", "obligations": []}),
            ])
            T("O1 好样本（BLOCK）完整渲出（渲染通路活着，反向对照不是恒红）",
              rendered[0] == (True, False, False), str(rendered[0]))
            T("O2 ★ state=ERROR 的 IR 不许渲染（报告与群消息都拦下）",
              rendered[1] == (False, True, True), str(rendered[1]))
            T("O3 ★ state=null 的 IR 不许渲染",
              rendered[2] == (False, True, True), str(rendered[2]))
        except Exception as e:  # noqa: BLE001
            T("O0 渲染器跑不起来（%s）—— 未测，不许当绿" % e, False, "")

    # ── P candidate 与 L0（验收行 31 反向对照）─────────────────────
    r_p_l0 = decide(inp(findings=[F("cp", status="candidate", sev="L0", auth=None)]))
    T("P1 ★ candidate+L0 必须正常出结论（链 13 REVIEW）—— I4 只对 confirmed",
      r_p_l0["run_state"] == "OK" and r_p_l0["state"] == "REVIEW"
      and r_p_l0["chain"] == 13, str(r_p_l0))
    T("P2 candidate+L0 不贡献严重度（max_sev=none，不是被当成最小值跳过）",
      r_p_l0.get("max_sev") == "none", str(r_p_l0.get("max_sev")))
    r_c_l5 = decide(inp(findings=[F("cp", status="candidate", sev="L5", auth=None)]))
    T("P3 candidate+L5 同样正常出结论（反向对照不是只挑 L0 一个点）",
      r_c_l5["run_state"] == "OK" and r_c_l5["state"] == "REVIEW"
      and r_c_l5["chain"] == 13, str(r_c_l5))

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


# ── --controls：新断言的反向对照 ─────────────────────────────────────────
# ★ 本脚本主检查里的 T() 全部是「对生产代码断言」，自己没有坏样本可喂；
#   这里的对照走「纯函数构件 + 打桩/坏样本」：每条新断言都要指得出
#   「喂什么必须红」。没红过的断言不算验证过它（AGENTS §2.4.1）。
def _expected_row_for(row):
    """N 段对拍用的独立期望表（不复用生产常量）。"""
    return {"chain": row[1], "state": row[2], "layer": row[3]}


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

    print("verify_decision_table · --controls（新断言的反向对照）")

    # C-L：坏样本必须红（L1–L6/L10 的反向面）。
    try:
        finding_store_check(_fs_record(detected_by="P2"))
        p2_ok = True
    except Exception as e:  # noqa: BLE001
        p2_ok = False
        print("     （P2 意外被拒：%s）" % e)
    C("CL1 域内 P2 必须被生产接受（否则 L3/L4 的「拒收」就是全拒的恒真）", p2_ok)
    for name, over in (
            ("CL2 P4 必须被拒（喂坏样本）", dict(detected_by="P4")),
            ("CL3 「高危」必须被拒", dict(detected_by="高危")),
            ("CL4 P5 必须被拒", dict(detected_by="P5")),
            ("CL5 L6 必须被拒", dict(severity="L6")),
            ("CL6 L9 被拒", dict(severity="L9")),
    ):
        C(name, finding_store_check(_fs_record(**over)) is not None,
          str(finding_store_check(_fs_record(**over))))

    # C-M：把生产 _AUTH_RANK 打坏（临时副本）→ M6/M7 的对拍构件必须报出。
    # ★ 打坏的方式必须是「conflict 与 expired 互换」（判据原文的变异形状）；
    #   互换 missing/expired 是判据明说未定的（行 30：缺失与过期谁优先未定），
    #   那种互换不许被当成坏样本（会教人写一个恒红断言）。
    src = _dt_text()
    bad_rank = src.replace(
        '_AUTH_RANK = {"ok": 0, "missing": 1, "expired": 2, "conflict": 3}',
        '_AUTH_RANK = {"ok": 0, "missing": 1, "expired": 3, "conflict": 2}')
    if bad_rank != src:
        ns = {"__name__": "dt_bad_rank"}
        try:
            exec(compile(bad_rank, "decision_table_bad.mjs", "exec"), ns)
            r = ns["decide"](inp(findings=[_f("o1", auth="expired"),
                                           _f("o2", auth="conflict")]))
            C("CM1 _AUTH_RANK 打坏后 M6 的构件必须读到 expired（不许恒真）",
              r.get("max_sev_authority") == "expired", str(r.get("max_sev_authority")))
        except Exception as e:  # noqa: BLE001
            C("CM1 _AUTH_RANK 打坏后构件读不出", False, str(e))
    else:
        C("CM1 找不到 _AUTH_RANK 原文（生产代码变了，对照过期）", False, "")

    # C-N：N1 结构钉的坏副本必须红。
    for name, mutated in (
            ("CN1 兜底改 PASS 的坏副本 → 结构钉红",
             src.replace(NO_CHAIN_SNIPPET,
                         'return {"run_state": "OK", "state": "PASS", "external_label": '
                         '"PASS", "layer": "DP1", "obligations": [], '
                         '"invariant_violation": None, "chain": 15}')),
            ("CN2 兜底整段删掉的坏副本 → 结构钉红（else 壳不完整）",
             src.replace("    else:\n        # 合法输入域上 15 条链应覆盖全部组合；"
                         "走到这里说明表漏了一条。\n        " + NO_CHAIN_SNIPPET + "\n",
                         "")),
            ("CN3 兜底改成 return None 的坏副本 → 结构钉红",
             src.replace(NO_CHAIN_SNIPPET, "return None")),
    ):
        try:
            problems, _ = no_chain_pins(mutated)
            C(name, problems != [], str(problems))
        except Exception as e:  # noqa: BLE001
            C(name, False, "构件抛异常：%s" % e)
    good_problems, good_flags = no_chain_pins(src)
    C("CN4 好副本结构钉零红（反向对照不许恒红）", good_problems == [],
      str(good_problems))
    C("CN5 好副本 PASS 旗全部在白名单（N2 的正向面）",
      all(n in PASS_FLAG_ALLOW for n, _ in good_flags), str(good_flags))
    C("CN6 陌生旗进不了白名单（PASS_FLAG_ALLOW 收窄探针）",
      "sneaky_pass_flag" not in PASS_FLAG_ALLOW, "")
    C("CN7 N4 穷举在真生产上必须零 NO_CHAIN（否则 N4 恒红成摆设）",
      exhaustive_no_chain_scan()[1] == [], "")

    # C-O：真实渲染器 —— 好样本绿、ERROR/null 坏样本红。node 不在 → 未测。
    if not _node_available():
        untested += 1
        print("  ⚠ CO 未测：node 不可用")
    else:
        try:
            res = _render_via_node([
                _render_snapshot({"state": "BLOCK", "layer": "DP2",
                                  "release_status": "待放行", "obligations": []}),
                _render_snapshot({"state": "ERROR", "layer": None,
                                  "release_status": "待放行", "obligations": []}),
                _render_snapshot({"state": None, "layer": None,
                                  "release_status": "待放行", "obligations": []}),
            ])
            C("CO1 好样本（BLOCK）完整渲出（正向）", res[0] == (True, False, False),
              str(res[0]))
            C("CO2 ERROR-IR 必须被拦（喂坏样本）", res[1] == (False, True, True),
              str(res[1]))
            C("CO3 null-IR 必须被拦（喂坏样本）", res[2] == (False, True, True),
              str(res[2]))
        except Exception as e:  # noqa: BLE001
            untested += 1
            print("  ⚠ CO 未测：渲染器跑不起来（%s）" % e)

    # C-P：candidate+L0 反向对照（P1 的正向已在主检查；这里喂「I4 误伤
    # candidate」的坏实现形状 —— 用临时副本打桩证明 P1 的判据写得出来）。
    bad_i4 = src.replace(
        'if any(f.get("status") == "confirmed" and f.get("severity") == "L0" for f in findings):',
        'if any(f.get("severity") == "L0" for f in findings):')
    if bad_i4 != src:
        try:
            ns2 = {"__name__": "dt_bad_i4"}
            exec(compile(bad_i4, "decision_table_badi4.py", "exec"), ns2)
            r = ns2["decide"](inp(findings=[_f("cp", status="candidate",
                                               sev="L0", auth=None)]))
            C("CP1 I4 误伤 candidate 的坏实现必须被 P1 判据读到（run_state=ERROR）",
              r.get("run_state") == "ERROR", str(r.get("run_state")))
        except Exception as e:  # noqa: BLE001
            C("CP1 坏实现跑不起来", False, str(e))
    else:
        C("CP1 找不到 I4 判定原文（生产代码变了，对照过期）", False, "")

    print("\n%s --controls %d 过 · %d 红 · %d 未测"
          % ("✅" if fail == 0 else "❌", ok, fail, untested))
    return ok, fail, untested


def _usage():
    print("用法：python3 tools/verify_decision_table.py [--controls]")


if __name__ == "__main__":
    if "--controls" in sys.argv:
        _ok, _fail, _untested = run_controls()
        sys.exit(1 if _fail else (2 if (_untested and not _ok) else 0))
    if any(a.startswith("-") and a not in ("--controls", "-h", "--help")
           for a in sys.argv[1:]):
        _usage()
        sys.exit(2)
    sys.exit(main())
