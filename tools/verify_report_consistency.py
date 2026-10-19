#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_report_consistency.py —— C-59：md 报告 ↔ ReviewIR 独立对拍

不把断言放在 `tools/audit/report_render.mjs` 里（渲染器不能自证），而是：
  - 用真实渲染器生成报告；
  - 本验证器**自己解析** finding_id / control_code / decision.state 与 IR 对拍；
  - 再断言 `ReportStore.publish` 对不一致文本**物理阻断**（不落盘、不给 URL）。

退出码：0 全过 / 1 有红 / 2 未测（Node 不可用、临时目录建不出）。
"""
from __future__ import annotations

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
    from report_store import ReportStore, rendered_report_mismatches
except Exception as e:  # noqa: BLE001
    print("❌ 导入 base/report_store.py 失败：%s" % e)
    sys.exit(1)

FIVE = {"BLOCK", "REVIEW", "未审查", "待自决", "PASS"}
FINDING_RE = re.compile(r"^\s*-\s+(\S+)\s+·\s*控制点：\s*(\S+)", re.M)
STATE_RE = re.compile(r"^\s*-\s*状态：\s*(.+?)\s*$", re.M)


def ir_fixture():
    return {
        "ir_id": "ir-c59", "ir_version": "review-ir-v1",
        "source_ir_version": "cu-c59",
        "content_unit_ref": {"unit_id": "cu-c59", "kind": "free_text"},
        "findings": [{
            "finding_id": "f1", "control_code": "H01", "status": "confirmed",
            "severity": "L4", "produced_by": "rule", "detected_by": "P0",
            "quote": "治疗", "authority_state": "ok",
            "location": {"kind": "text_span", "start": 0, "end": 2},
        }],
        "decision": {"state": "BLOCK", "layer": "DP2",
                     "release_status": "待放行", "obligations": []},
        "coverage": {"coverage_state": "partial",
                     "modalities_evaluated": ["free_text"],
                     "rules_version": "rs-c59",
                     "control_points_applied": ["H01"]},
        "receipt_ref": "rc-c59", "rule_snapshot": "rs-c59",
        "kb_snapshot": "kb-c59", "control_points_version": "cp-c59",
        "created_at": "2026-10-19T00:00:00Z",
    }


def snapshot(ir):
    return {
        "ir": ir,
        "failure_kind_counts": {"fetch_error": 0, "parse_error": 0,
                                "empty": 0, "unsupported": 0},
        "unknown_bucket_counts": {},
        "evidence": [],
        "unassessed": [],
        "receipt": {"skill": "s", "version": "1", "fingerprint": "f" * 64,
                    "skipped_steps": "无", "rule_snapshot": "rs-c59"},
        "report_url": "https://static.example.com/reports/x.md",
    }


def independent_mismatches(ir, text):
    """验证器自己的解析器（不调用被测模块的对拍函数）。"""
    errs = []
    if not isinstance(text, str) or not text:
        return ["unparsable:empty"]
    lines = FINDING_RE.findall(text)
    want = [(f["finding_id"], f["control_code"]) for f in ir["findings"]]
    if want and not lines:
        return ["unparsable:no_finding_lines"]
    got = {(fid, code) for fid, code in lines}
    if set(want) != got:
        errs.append("findings_mismatch:want=%r got=%r" % (sorted(want), sorted(got)))
    states = [s.strip() for s in STATE_RE.findall(text)]
    if not states:
        errs.append("unparsable:no_state_line")
    elif states[0] != ir["decision"]["state"]:
        errs.append("state_mismatch:%r!=%r" % (states[0], ir["decision"]["state"]))
    elif any(s != ir["decision"]["state"] for s in states):
        errs.append("state_conflict:%r" % (states,))
    return errs


def main():
    if not shutil.which("node"):
        print("⚠ 未测：找不到 node")
        return 2
    try:
        TMP = tempfile.mkdtemp(prefix="report-consistency-")
    except OSError as e:
        print("⚠ 未测：建不出临时目录（%s）" % e)
        return 2

    fails = []
    checks = 0

    def T(cid, ok, detail=""):
        nonlocal checks
        checks += 1
        if not ok:
            fails.append("%s  %s" % (cid, detail))

    ir = ir_fixture()
    runner = os.path.join(TMP, "render.mjs")
    mod = "file://" + os.path.join(ROOT, "tools", "audit", "report_render.mjs")
    with open(runner, "w", encoding="utf-8") as f:
        f.write(
            "import { renderReport } from %r;\n"
            "let input='';\n"
            "for await (const c of process.stdin) input += c;\n"
            "process.stdout.write(JSON.stringify(renderReport(JSON.parse(input))));\n"
            % mod)
    p = subprocess.run(["node", runner], input=json.dumps(snapshot(ir), ensure_ascii=False),
                       text=True, capture_output=True)
    T("C0 真实渲染器产出报告", p.returncode == 0 and bool(p.stdout), p.stderr[-300:])
    try:
        out = json.loads(p.stdout)
    except ValueError:
        out = {}
    md = out.get("markdown") or ""
    T("C0b 渲染 ok", out.get("ok") is True, str(out.get("errors"))[:300])

    # 1) 正样本：验证器独立解析与 store 对拍都必须零不一致
    T("C1 独立解析：正样本零不一致", independent_mismatches(ir, md) == [],
      str(independent_mismatches(ir, md)))
    T("C1b store 对拍：正样本零不一致", rendered_report_mismatches(ir, md) == [],
      str(rendered_report_mismatches(ir, md)))

    # 1c) ★ C-78 ①：报告渲染的键必须是 control_code / rule_key，**不是分类条目**
    #
    #   ★ 这一条与 V62c/V62d 是两层：那两条扫**源码文本**（静态），
    #     这一条看**实际渲染出来的文本**（行为）。
    #     源码里有 `control_code` 但模板没把它渲染出来，静态扫描照样绿 ——
    #     所以必须真的跑一遍渲染器再读输出。
    T("C1c 渲染输出里每个 finding 都带 control_code",
      bool(ir["findings"]) and all(
          re.search(r"控制点：\s*" + re.escape(f["control_code"]), md)
          for f in ir["findings"]),
      "md 里没找到 control_code")

    T("C1d ★ 渲染输出里不出现 subclass（分类条目只是视图，不是键）",
      "subclass" not in md, "md 里出现了 subclass")

    # ★ 反向对照：给 finding 塞一个 subclass_code，渲染器**不许**拿它当键。
    #   若渲染器改成了 `f.subclass_code || f.control_code`，这条会红。
    ir_sub = json.loads(json.dumps(ir))
    ir_sub["findings"][0]["subclass_code"] = "SC-99"
    with open(runner, "w", encoding="utf-8") as f:
        f.write(
            "import { renderReport } from %r;\n"
            "let input='';\n"
            "for await (const c of process.stdin) input += c;\n"
            "process.stdout.write(JSON.stringify(renderReport(JSON.parse(input))));\n"
            % mod)
    p2 = subprocess.run(["node", runner],
                        input=json.dumps(snapshot(ir_sub), ensure_ascii=False),
                        text=True, capture_output=True)
    md_sub = (json.loads(p2.stdout).get("markdown") if p2.returncode == 0 and p2.stdout else "") or ""
    T("C1e ★ 反向对照：带 subclass_code 时仍以 control_code 为键",
      bool(md_sub) and "SC-99" not in md_sub and "H01" in md_sub,
      "subclass 被当成了键，或渲染失败")

    # 2) 三种错配：finding_id / control_code / state
    bad_id = md.replace("- f1 · 控制点：H01", "- fX · 控制点：H01")
    bad_code = md.replace("- f1 · 控制点：H01", "- f1 · 控制点：H99")
    bad_state = md.replace("- 状态：BLOCK", "- 状态：PASS")
    for cid, text, why in (
        ("C2 finding_id 不一致", bad_id, "finding_id"),
        ("C2b control_code 不一致", bad_code, "control_code"),
        ("C2c decision.state 不一致", bad_state, "state"),
    ):
        T(cid + " → 独立解析红", independent_mismatches(ir, text) != [], why)
        T(cid + " → store 对拍红", rendered_report_mismatches(ir, text) != [], why)

    # 3) 格式变了/清空：解析不到 finding 行不能当「零不一致」
    empty = ""
    no_findings = re.sub(r"^\s*-\s+\S+\s+·\s*控制点：.*$", "", md, flags=re.M)
    for cid, text in (("C3 空文本", empty), ("C3b 删掉 finding 行", no_findings)):
        T(cid + " → 独立解析红", independent_mismatches(ir, text) != [], "")
        T(cid + " → store 报 unparsable",
          any(x.startswith("ir_render_unparsable")
              for x in rendered_report_mismatches(ir, text)),
          str(rendered_report_mismatches(ir, text)))

    # 4) publish 阻断：不一致不落盘、不追加索引、不给 URL
    acl = {"tenant": "t1", "product_line": "p1",
           "submitter_id": "u1", "assigned": []}
    store = ReportStore(os.path.join(TMP, "data_ok"), "https://static.example.com")
    good = store.publish(ir, lambda _ir: md, acl)
    T("C4 正样本正常发布", good.get("ok") is True and good.get("url"), str(good))

    for cid, text, want_detail in (
        ("C5 不一致文本", bad_id, "ir_render_mismatch"),
        ("C5b 空文本", empty, "ir_render_unparsable"),
    ):
        st = ReportStore(os.path.join(TMP, "data_" + str(abs(hash(cid)) % 10**8)),
                         "https://static.example.com")
        r = st.publish(ir, lambda _ir, t=text: t, acl)
        idx = st.read_index()
        files = os.listdir(os.path.join(st.root, "reports"))
        T(cid + " → publish 阻断且不给 URL",
          r.get("ok") is False and r.get("url") is None
          and str(r.get("detail", "")).startswith(want_detail), str(r))
        T(cid + " → 没有落盘/索引",
          not any(x.endswith(".md") for x in files) and idx["records"] == [],
          "files=%r idx=%r" % (files, idx["records"]))

    for f in fails:
        print("  ❌ " + f)
    verdict = "❌" if fails else "✅"
    print("\n%s verify_report_consistency %d 项检查 · %d 项红" % (verdict, checks, len(fails)))
    print("  md 长度 %d；IR findings %d；state=%s"
          % (len(md), len(ir["findings"]), ir["decision"]["state"]))
    shutil.rmtree(TMP, ignore_errors=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
