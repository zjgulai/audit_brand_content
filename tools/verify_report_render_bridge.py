#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_report_render_bridge.py - T-316c: render adaptor layer.

## Why this file exists

`ReportStore.publish(ir, render_fn, acl)` takes a `render_fn(ir)`.
The only renderer in the repo is `tools/audit/report_render.mjs` and its
entry point is `renderReport(snapshot)` - it takes the **five-key snapshot**,
not `ir`. So between "we have a snapshot in authority state" (T-316b, done)
and "ReportStore can publish it" there was a **missing adaptor**.

Measured 2026-10-24: `grep -rn 'report_render.mjs' --include=*.py base/`
-> 0 hits. Nothing in `base/` could render a report at all.

## The four constraints and how each one goes red

    B1  real renderer produces six blocks + R1 line + 64-hex fingerprint
    B2  node missing -> {ok:False, detail:"node_missing"}, NO exception
    B3  renderer missing -> {ok:False, detail:"renderer_missing"}
    B4  renderer rejects bad snapshot -> ok False, errors non-empty
    B5  timeout is explicit and bites (timeout=0.001 on a real render)
    B6  snapshot travels on stdin, not argv (byte-compare what node saw)
    B7  output normalisation: ok must be literally True; empty markdown is a failure
    B8  no retry (a failing renderer is run exactly once)
    B9  bad input never raises (non-dict, non-serialisable)
    B10 renderer crash -> detail carries the exit code, stderr tail kept

Exit codes: 0 all pass / 1 red / 2 untested (no node).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from base.report_render_bridge import (
        ReportRenderBridge, render_snapshot, _normalize, DEFAULT_RENDERER)
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: cannot import bridge: %s" % exc)
    sys.exit(2)

SUBJECTS = ("base/report_render_bridge.py", "tools/audit/report_render.mjs")


def snapshot(state="PASS", coverage="full", findings=None):
    return {
        "ir": {
            "ir_id": "ir-b1", "ir_version": "content-unit-v1",
            "decision": {"state": state, "release_status": "待放行",
                         "basis": "规则+L1"},
            "coverage": {"coverage_state": coverage,
                         "modalities_evaluated": ["字幕", "关键帧"],
                         "rules_version": "rules-v1",
                         "control_points_applied": 7},
            "findings": findings or [],
        },
        "failure_kind_counts": {"fetch_error": 0, "parse_error": 0,
                                "empty": 0, "unsupported": 0},
        "unknown_bucket_counts": {},
        "evidence": [], "unassessed": [],
        "receipt": {"skill": "content-review", "version": "1.0",
                    "fingerprint": "f" * 64, "skipped_steps": "无",
                    "rule_snapshot": "rs-b1"},
    }


def main():
    passed = failed = 0

    def report(ok, name, detail=""):
        nonlocal passed, failed
        ok = bool(ok)
        print(("PASS" if ok else "FAIL") + ": " + name +
              ((" " + detail) if detail else ""),
              file=sys.stdout if ok else sys.stderr)
        passed += int(ok)
        failed += int(not ok)

    b = ReportRenderBridge(ROOT)
    if b.node() is None:
        print("UNTESTED: node not on PATH")
        return 2

    # ---- B1 a real render ----
    try:
        r = b.render(snapshot())
    except Exception as exc:  # noqa: BLE001
        r = {"ok": False, "detail": "raised:%s" % type(exc).__name__}
    md = r.get("markdown") or ""
    blocks = ["## 结论", "## 命中的问题", "## 覆盖证明",
              "## 依据清单", "## 未审说明", "## 执行回执"]
    report(r.get("ok") is True and all(x in md for x in blocks),
           "B1 real renderer -> ok + six blocks",
           "ok=%r missing=%r" % (r.get("ok"), [x for x in blocks if x not in md]))
    import re
    r1 = re.search(r"source_ir_fingerprint:\s*([0-9a-f]{64})", md)
    report(r1 is not None, "B1b R1 fingerprint line is 64 hex",
           repr(md.splitlines()[2] if len(md.splitlines()) > 2 else ""))

    # ---- B2 node missing must not raise ----
    try:
        miss = ReportRenderBridge(ROOT, node_path="").render(snapshot())
        raised = None
    except Exception as exc:  # noqa: BLE001
        miss, raised = None, "%s: %s" % (type(exc).__name__, exc)
    report(raised is None and miss.get("ok") is False
           and miss.get("detail") == "node_missing",
           "B2 ★ node missing -> {ok:False, detail:node_missing}, no exception",
           repr(raised or miss))

    # ---- B3 renderer missing ----
    r3 = ReportRenderBridge(ROOT, renderer=os.path.join(
        tempfile.gettempdir(), "no-such-renderer-%d.mjs" % os.getpid())).render(snapshot())
    report(r3.get("ok") is False and r3.get("detail") == "renderer_missing",
           "B3 renderer missing -> renderer_missing", repr(r3))

    # ---- B4 renderer rejects ----
    r4 = b.render({"ir": {}})
    report(r4.get("ok") is False and r4.get("errors")
           and r4.get("markdown") == "",
           "B4 bad snapshot rejected by renderer (bridge does not validate)",
           repr(r4.get("errors"))[:120])

    # ---- B5 timeout bites ----
    r5 = ReportRenderBridge(ROOT, timeout=0.001).render(snapshot())
    report(r5.get("ok") is False and str(r5.get("detail", "")).startswith(
               "render_timeout"),
           "B5 ★ timeout is explicit and bites (no hang)", repr(r5.get("detail")))

    # ---- B6 stdin, not argv ----
    #
    # ★ 这一条第一版写错了两次，写下来是因为它是个好例子：
    #   1. 探针没导出 `renderReport` → 红，但红的是「探针不合契约」。
    #   2. 探针在模块顶层自己 `for await (const c of process.stdin)` ——
    #      它和桥接层 runner 抢同一个 stdin，runner 读到空串，
    #      JSON.parse('') 抛错 → 又红，这次红的是「两个读者抢一条流」。
    #
    # 正确的测法：**从被调方能看到的事实反推**。
    # 探针拿到 `snapshot` 参数，它只需要回答两件事：
    #   ① 收到的对象与送出的**逐字节等价**（canonical JSON 相同）→ 走的是 stdin；
    #   ② 整个 `process.argv` 里没有 payload 的特征串 → 没走 argv。
    d6 = tempfile.mkdtemp(prefix="bridge-stdin-")
    probe = os.path.join(d6, "probe.mjs")
    probe_src = (
        "export function renderReport(snapshot){\n"
        "  const blob = JSON.stringify(snapshot);\n"
        "  const inArgv = process.argv.some(a => a.includes('MARKER_9f3a'));\n"
        "  return {ok:true, errors:[], markdown: JSON.stringify({\n"
        "    argv_has_marker: inArgv,\n"
        "    marker_value: snapshot && snapshot.marker,\n"
        "    got_keys: Object.keys(snapshot || {}).sort(),\n"
        "    blob_len: blob.length }) };\n"
        "}\n")
    Path(probe).write_text(probe_src, encoding="utf-8")
    snap6 = snapshot()
    snap6["marker"] = "MARKER_9f3a"
    r6 = ReportRenderBridge(ROOT, renderer=probe).render(snap6)
    try:
        seen = json.loads(r6.get("markdown") or "{}")
    except ValueError:
        seen = {}
    # ★ 不比 `blob_len`：Python 的 `json.dumps` 默认带 `", "` 与 `": "` 分隔符，
    #   node 的 `JSON.stringify` 不带 —— 跨语言比字节数会得到一个恒假的条件，
    #   而恒假的条件看起来像「B6 抓到了一个真缺陷」。
    #   要比的是**内容等价**：键集合一致、特征值原样到达、argv 里没有。
    #   需要字节级等价时用 JCS canonical（两边各有实现），但那属于契约测试。
    report(r6.get("ok") is True
           and seen.get("argv_has_marker") is False
           and seen.get("marker_value") == "MARKER_9f3a"
           and seen.get("got_keys") == sorted(snap6)
           and seen.get("blob_len", 0) > len(snap6),
           "B6 ★ snapshot arrives whole via stdin and is absent from argv",
           repr(seen) or repr(r6))

    # ---- B7 normalisation ----
    report(_normalize({"ok": "true", "markdown": "# x"})["ok"] is False,
           "B7a ★ string 'true' is not True (no truthy shortcut)",
           repr(_normalize({"ok": "true", "markdown": "# x"})))
    report(_normalize({"ok": True, "markdown": ""})["ok"] is False
           and _normalize({"ok": True, "markdown": ""})["detail"] == "empty_markdown",
           "B7b ★ ok=True with empty markdown is a failure",
           repr(_normalize({"ok": True, "markdown": ""})))
    report(_normalize("not a dict")["detail"] == "bad_output",
           "B7c non-object output -> bad_output", repr(_normalize("x")))
    report(_normalize({"ok": False, "markdown": "# leaked"})["markdown"] == "",
           "B7d ★ failed render must not leak markdown downstream",
           repr(_normalize({"ok": False, "markdown": "# leaked"})))

    # ---- B8 no retry ----
    counter = os.path.join(d6, "count.txt")
    once = os.path.join(d6, "once.mjs")
    Path(once).write_text(
        "import {appendFileSync} from 'node:fs';\n"
        "export function renderReport(){"
        " appendFileSync(%s, 'x');"
        " return {ok:false,markdown:'',errors:['boom']}; }\n"
        % json.dumps(counter), encoding="utf-8")
    for i in range(3):
        ReportRenderBridge(ROOT, renderer=once).render(snapshot())
    calls = len(Path(counter).read_text()) if os.path.exists(counter) else 0
    report(calls == 3, "B8 no retry: 3 renders -> exactly 3 invocations",
           "calls=%d" % calls)

    # ---- B9 bad input never raises ----
    bad_ok, bad_detail = True, ""
    for bad in (None, [], "str", 42, {"x": object()}):
        try:
            out = b.render(bad)
            if not isinstance(out, dict) or out.get("ok") is not False:
                bad_ok, bad_detail = False, repr(out)
        except Exception as exc:  # noqa: BLE001
            bad_ok, bad_detail = False, "raised %s" % type(exc).__name__
    report(bad_ok, "B9 ★ bad input never raises (returns ok False)", bad_detail)

    # ---- B10 renderer crash ----
    crash = os.path.join(d6, "crash.mjs")
    Path(crash).write_text(
        "export function renderReport(){"
        " process.stderr.write('kaboom'); process.exit(7); }\n",
        encoding="utf-8")
    r10 = ReportRenderBridge(ROOT, renderer=crash).render(snapshot())
    report(r10.get("ok") is False and r10.get("detail") == "render_exit:7"
           and any("kaboom" in str(e) for e in r10.get("errors") or []),
           "B10 ★ crash -> detail carries exit code + stderr tail", repr(r10))

    # ---- B11 module-level convenience matches the class ----
    r11 = render_snapshot(snapshot(), repo_root=ROOT)
    report(r11.get("ok") is True, "B11 render_snapshot() equals bridge.render()",
           "ok=%r" % r11.get("ok"))

    print("----------------------------------------")
    if failed == 0:
        print("OK %d/%d passed" % (passed, passed + failed))
        return 0
    print("FAILED %d passed, %d failed" % (passed, failed), file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: verifier crashed: %s" % exc)
        sys.exit(2)
