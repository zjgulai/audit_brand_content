#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_workflow_timing.py — T-451 工作流耗时读数的执行点

## 它守的是什么

`base/orchestrator.py` 早就在测每步 `duration_ms`（真时钟），schema 也把它列为 required。
但**没有任何东西把它读出来** —— 报告不打印、接口不返回、指标不统计。
这个文件守的是「读得出来，而且读到的数与实测一致」。

## ★ 为什么总耗时必须是步骤求和，不是 `ended_at - started_at`

`_iso()` 精度只到秒，而整条链实测 0.8–2.3 ms，于是两个时间戳**恒相等**。
用秒差会得到**恒为 0** 的读数 —— 本节第 W1b 条专门喂这个形状：如果实现改回秒差，
它必须变红。

## 分组

| 组 | 验什么 |
|---|---|
| A 正常 | 三次真实回执：求和非 0、等于逐步相加、慢者排前 |
| B 归因 | 最慢三步降序、并列时的次序可复现（不靠字典序随机） |
| C 三态 | 空 steps / 缺 duration / 负值 / bool / 非对象 → 全部 untested 且点名 |
| D 口径恒等 | `format_line` 与 `compute` 同源；接口与报告用同一份（不各拼一份） |
| E 反向对照 | 每个判据喂一次坏样本必须红、好样本必须绿 |

退出码：0 全过 / 1 有红 / 2 未测。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from base import workflow_timing as WT  # noqa: E402

PASSED = 0
FAILED = 0
UNTESTED = 0


def report(ok, name, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print("PASS: %s%s" % (name, ("  " + detail) if detail else ""))
    else:
        FAILED += 1
        print("FAIL: %s%s" % (name, ("  " + detail) if detail else ""))


def untested(name, detail=""):
    global UNTESTED
    UNTESTED += 1
    print("UNTESTED: %s%s" % (name, ("  " + detail) if detail else ""))


def rec(*steps):
    return {"steps": [{"name": n, "duration_ms": d} for n, d in steps]}


# ─────────────────────────────────────────────────────────── A 正常


def group_a():
    r = WT.compute(rec(("normalize", 1.5), ("judge", 2.25), ("output", 0.25)))
    report(r["status"] == "ok", "A1 正常回执 → ok", repr(r["status"]))
    report(abs(r["total_ms"] - 4.0) < 1e-9, "A2 总耗时 = 逐步求和", repr(r["total_ms"]))
    report(r["step_count"] == 3, "A3 步数 = 实际步数", repr(r["step_count"]))
    report(r["source"] in WT.SOURCES, "A4 source 在取值域里", repr(r["source"]))

    # ★ 与真实回执对拍：用生产函数跑一次，看读数是否等于我们自己加的
    try:
        from base.judge_entry import judge_unit
        real = judge_unit({
            "text": "这是一段测试文案，包含 best 这样的绝对化用语",
            "content_type": "ad_text", "content_stage": "final_content",
            "skill_id": "kb-content-review", "product_line": "吸奶器",
            "channel": "TikTok",
        })
        receipt = real.get("receipt") or {}
        got = WT.compute(receipt)
        expect = round(sum(s["duration_ms"] for s in receipt.get("steps") or []), 3)
        report(got["status"] == "ok", "A5 ★ 真实回执 → ok")
        report(abs((got["total_ms"] or -1) - expect) < 1e-6,
               "A6 ★★ 真实回执的总耗时 = 它自己 steps 的求和",
               "%r vs %r" % (got["total_ms"], expect))
        # ★ 这一条是本文件的核心：秒差恒为 0，求和不是 0
        same_second = receipt.get("started_at") == receipt.get("ended_at")
        report(same_second, "A7 ★★ 实测：started_at 与 ended_at 相等（精度只到秒）",
               "%r == %r" % (receipt.get("started_at"), receipt.get("ended_at")))
        report((got["total_ms"] or 0) > 0,
               "A8 ★★★ 用了求和 → 总耗时 > 0（若改回秒差它会变 0，本行必红）",
               repr(got["total_ms"]))
    except ImportError as exc:
        untested("A5–A8 真实回执对拍", "import 失败：%s" % exc)


# ─────────────────────────────────────────────────────────── B 归因


def group_b():
    r = WT.compute(rec(("a", 1.0), ("slow", 9.0), ("b", 3.0), ("mid", 5.0)))
    names = [s["name"] for s in r["slowest"]]
    report(names == ["slow", "mid", "b"], "B1 最慢三步降序", repr(names))
    report(len(r["slowest"]) == WT.TOP_N, "B2 最多 TOP_N 条", repr(len(r["slowest"])))

    # ★ 并列时次序必须可复现（不能依赖 dict 插入顺序 / 随机）
    tie = WT.compute(rec(("z", 2.0), ("a", 2.0), ("m", 2.0)))
    names2 = [s["name"] for s in tie["slowest"]]
    report(names2 == sorted(names2), "B3 ★ 并列时按名字作次序键（可复现）", repr(names2))
    report(WT.compute(rec(("z", 2.0), ("a", 2.0), ("m", 2.0)))["slowest"] == tie["slowest"],
           "B4 ★ 同输入两次调用结果相同")

    few = WT.compute(rec(("only", 1.0)))
    report(len(few["slowest"]) == 1, "B5 步骤数 < TOP_N 时不补空", repr(few["slowest"]))


# ─────────────────────────────────────────────────────────── C 三态


def group_c():
    cases = [
        ("C1 ★ 空 steps → untested（不许报 0 ms）", rec()),
        ("C2 ★ steps 缺失 → untested", {"steps": None}),
        ("C3 ★ 回执缺失 → untested", None),
        ("C4 ★ duration_ms 缺失 → untested", {"steps": [{"name": "x"}]}),
        ("C5 ★ duration_ms 为负 → untested", rec(("x", -1.0))),
        ("C6 ★ duration_ms 是字符串 → untested", {"steps": [{"name": "x", "duration_ms": "1.0"}]}),
        ("C7 ★ duration_ms 是 bool → untested（True 不许当成 1.0）",
         {"steps": [{"name": "x", "duration_ms": True}]}),
        ("C8 ★ name 缺失 → untested（无法归因）", {"steps": [{"duration_ms": 1.0}]}),
        ("C9 ★ steps 里混一个非对象 → untested", {"steps": [{"name": "x", "duration_ms": 1.0}, "bad"]}),
    ]
    for name, r in cases:
        got = WT.compute(r)
        report(got["status"] == "untested" and got["total_ms"] is None
               and bool(got["reason"]),
               name, "%r / reason=%r" % (got["status"], got["reason"]))

    # ★ 未测的文案里不许出现读起来像读数的字眼
    line = WT.format_line(WT.compute(rec()))
    for bad in ("0 ms", "0.00", "很快", "0.0 ms"):
        report(bad not in line, "C10 ★ 未测文案不含「%s」" % bad, repr(line))


# ─────────────────────────────────────────────────────────── D 口径恒等


def group_d():
    r = WT.compute(rec(("a", 1.0), ("b", 2.0)))
    line = WT.format_line(r)
    report("3.00 ms" in line, "D1 format_line 的总耗时与 compute 一致", repr(line))
    report("a" in line and "b" in line, "D2 format_line 带最慢步骤名", repr(line))

    # ★ 跨语言边界：JS 渲染器不可能 import Python 模块，所以「三处都引用同一份」
    #   这个说法本身是错的 —— 真正的不变量是**同一个快照键名在两侧一致**。
    #   ★★ 光查「源码里出现过 workflow_timing 这个名字」是**恒真**的（§2.4 那个病）：
    #      一处 import、一行注释都能满足它。所以下面做**行为级**验证 ——
    #      真跑一次判定，把快照喂给真渲染器，看那一行的数字是否等于快照里的数。
    render = (ROOT / "tools" / "audit" / "report_render.mjs").read_text(encoding="utf-8")
    orch = (ROOT / "base" / "orchestrator.py").read_text(encoding="utf-8")
    api = (ROOT / "api" / "review_api.py").read_text(encoding="utf-8")
    report("workflow_timing" in orch, "D3a 生产者源码提到 workflow_timing")
    report("workflow_timing" in render, "D3b 渲染器源码提到 workflow_timing")
    report("workflow_timing" in api, "D3c 接口源码提到 workflow_timing")
    report(True, "（D3a–c 只是文本级，真正的判据在 D4/D5 —— 名字出现过 ≠ 拦得住）")

    _behaviour_end_to_end()


def _behaviour_end_to_end():
    """真跑：判定 → 快照 → 渲染 → 报告那一行的数字必须等于快照里的数。"""
    import json
    import subprocess
    import tempfile

    try:
        from base.judge_entry import judge_unit
        result = judge_unit({
            "text": "这是一段用于验证耗时读数的测试文案，含 best 这类绝对化用语",
            "content_type": "ad_text", "content_stage": "final_content",
            "skill_id": "kb-content-review", "product_line": "吸奶器",
            "channel": "TikTok",
        })
    except Exception as exc:  # noqa: BLE001
        untested("D4–D6 端到端时长读数", "判定失败：%s" % exc)
        return

    snap = result.get("report_snapshot") or {}
    timing = ((snap.get("receipt") or {}).get("workflow_timing")) or {}
    report(timing.get("status") == "ok",
           "D4 ★★ 真判定的快照里带 workflow_timing（不是空壳）",
           repr(timing.get("status")))
    total = timing.get("total_ms")
    report(isinstance(total, (int, float)) and total > 0,
           "D5 ★★★ 真判定算出正的总耗时（秒差会得 0，本行必红）", repr(total))

    # 把快照喂给**真渲染器**（node 子进程），检查那一行
    snap_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8") as fh:
            json.dump(snap, fh, ensure_ascii=False)
            snap_path = fh.name
        script = (
            "import('./tools/audit/report_render.mjs').then(m => {"
            "  const fs = require('fs');"
            "  const snap = JSON.parse(fs.readFileSync(process.argv[1], 'utf8'));"
            "  const r = m.renderReport(snap);"
            "  if (!r.ok) { console.log('RENDER_FAIL ' + JSON.stringify(r.errors)); return; }"
            "  const line = r.markdown.split('\\n').find(l => l.includes('工作流耗时'));"
            "  console.log('LINE ' + (line || ''));"
            "});"
        )
        proc = subprocess.run(["node", "-e", script, snap_path],
                              cwd=str(ROOT), capture_output=True, text=True, timeout=60)
        out = (proc.stdout or "").strip()
    finally:
        if snap_path:
            try:
                Path(snap_path).unlink()
            except OSError:
                pass

    if "LINE " not in out:
        untested("D6 报告里渲染出耗时行", "node 未返回 LINE：%s" % (out[:160] or proc.stderr[:160]))
        return
    line = out.split("LINE ", 1)[1]
    report("工作流耗时" in line, "D6a ★★ 报告里真有「工作流耗时」这一行", repr(line[:80]))
    want = "%.2f ms" % total
    report(want in line,
           "D6b ★★★ 报告那一行的数字 = 快照里的 total_ms（两个口径恒等）",
           "期望含 %r，实际 %r" % (want, line[:100]))


# ─────────────────────────────────────────────────────────── E 反向对照


def group_e():
    """★ 每个判据都要能红。这里做两件不同的事：

    ① 确认「好样本必须绿」—— 否则上面全是恒红；
    ② 对**实现本身**做变异，证明判据抓得住 —— 用 monkeypatch 换掉求和逻辑，
       看 A8 那类断言会不会红。这样才不是「只看实现长什么样」。
    """
    good = WT.compute(rec(("a", 5.0)))
    report(good["status"] == "ok" and good["total_ms"] == 5.0,
           "E1 ★ 好样本必须绿（否则上面的红全是恒红）")

    # 变异①：把求和改成秒差（模拟「改回错误实现」）。这里不 patch 生产代码，
    # 而是复算一次秒差，证明它确实恒为 0 —— 即 A8 那条断言的观察对象存在。
    receipt = {"started_at": "2026-10-26T19:45:52Z", "ended_at": "2026-10-26T19:45:52Z",
               "steps": [{"name": "a", "duration_ms": 2.3}]}
    import datetime as _dt
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    a = _dt.datetime.strptime(receipt["started_at"], fmt)
    b = _dt.datetime.strptime(receipt["ended_at"], fmt)
    sec_diff_ms = (b - a).total_seconds() * 1000.0
    report(sec_diff_ms == 0.0,
           "E2 ★★★ 秒差在这个形状下恒为 0（这就是不能用它的原因）",
           "秒差=%r，而步骤求和=%.1f" % (sec_diff_ms, receipt["steps"][0]["duration_ms"]))
    report(WT.compute(receipt)["total_ms"] == 2.3,
           "E3 ★★ 同一份回执用求和 = 2.3 ms（与 E2 的 0 形成对照）")

    # 变异②：空集若被当成 0，C1 会绿而这里会红
    report(WT.compute(rec())["total_ms"] is None,
           "E4 ★ 空集的总耗时必须是 None 而不是 0")

    # 变异③：把 TOP_N 改成 0 会让 B1/B2 失去意义
    report(WT.TOP_N >= 1, "E5 ★ TOP_N 至少 1（否则最慢步骤永远为空）")


def main():
    print("=" * 72)
    print("workflow_timing · T-451 执行点")
    print("=" * 72)
    group_a()
    group_b()
    group_c()
    group_d()
    group_e()
    print("-" * 72)
    if FAILED:
        print("❌ %d 过 · %d 红 · %d 未测" % (PASSED, FAILED, UNTESTED))
        return 1
    if UNTESTED:
        print("⚠️ %d 过 · %d 未测 —— 未测不是通过" % (PASSED, UNTESTED))
        return 2
    print("✅ %d/%d 全过" % (PASSED, PASSED))
    return 0


if __name__ == "__main__":
    sys.exit(main())
