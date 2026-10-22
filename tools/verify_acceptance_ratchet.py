#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_acceptance_ratchet.py —— T-145：验收执行门的**棘轮**判据

## 为什么需要「棘轮」而不是「全绿才算过」

`tools/verify_acceptance_run.py` 今天退 **2**（untested=20，其中 **7 条是 manual**）。
那 7 条在验收表里明写「不作为执行验收项 / 按人工验收」——
**它们永远不会变成 passed**。所以「CI 里 untested 必须为 0」这条判据，
今天不可能成立，明天也不会。

于是 CI 只有两种写法：

| 写法 | 后果 |
|---|---|
| 断言 `untested == 0` | **永远红**。红了三个月之后，所有人都会开始无视这条 CI |
| 断言 `failed == 0` 且 `passed` 不许倒退 | 棘轮：**今天的地板是今天的读数，只许往上** |

本脚本实现第二种。

## 棘轮的三条判据（缺一条就漏一类回归）

1. **`failed` 必须为 0** —— 任何一条红的验收项都不许合入。
2. **计数之和必须等于总行数**（136）—— 否则说明有人删了行或执行器少读了行，
   而 `passed` 可能同时还「没倒退」，看起来一切正常。
3. **`passed` 不得低于地板** —— 地板记在 `tools/acceptance-ratchet.json` 里，
   只能手动上调。**下调是一次有记录的决定，不是一次顺手改数字。**

> 第 2 条不是多余的：`passed=116 / failed=0 / untested=20` 与
> `passed=116 / failed=0 / untested=20`（表被删了 5 行，总数 131）
> 在头两条上都成立。**总数不卡，删行就永远不会红。**

## 它**不判**什么

* **不判** CI 真的在跑。本脚本只判「这一次的读数有没有倒退」。
  「CI 配置存在且引用执行器」是 `verify_acceptance_trigger.py` 的事，
  而**「远端真的拦住了合并」本机读不到**（无 `gh`、离线、带凭据详情 401）。
* **不判**那 7 条 manual 有没有人工验收过 —— 那是人做的，机器看不见。

## 输入

    # 从 stdin 读（CI 里的用法：跑一次执行器，把输出喂进来）
    python3 tools/verify_acceptance_run.py | python3 tools/verify_acceptance_ratchet.py

    # 或直接跑（本地一次搞定）
    python3 tools/verify_acceptance_ratchet.py --run

## 退出码

  0 棘轮成立（failed=0、总数对、passed ≥ 地板）
  1 有红（任一条判据不成立）
  2 未测（输出解析不出 / 地板文件读不出）—— **不是通过**
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RATCHET = ROOT / "tools" / "acceptance-ratchet.json"
RUNNER = ROOT / "tools" / "verify_acceptance_run.py"

#: 验收表的总行数。这是**结构常量**，不是读数 —— 表增删行时它会先红，
#: 那一刻要人来决定「这是增行还是误删」，不许自动跟随。
TOTAL_ROWS = 136

RE_COUNTS = re.compile(r"^passed=(\d+) failed=(\d+) untested=(\d+)$", re.M)
RE_SPLIT = re.compile(
    r"^untested_split: machine=(\d+) manual=(\d+) unverifiable=(\d+) unknown=(\d+)$", re.M)


class Untested(Exception):
    """读数解析不出 —— 退 2。不许当成「棘轮成立」。"""


def parse_counts(text: str) -> dict:
    """从执行器输出里解析三个计数 + 分账。解析不出 → Untested。"""
    m = RE_COUNTS.search(text)
    if not m:
        raise Untested("输出里没有 `passed=N failed=N untested=N` 那一行")
    passed, failed, untested = (int(m.group(i)) for i in (1, 2, 3))
    s = RE_SPLIT.search(text)
    split = None
    if s:
        split = {"machine": int(s.group(1)), "manual": int(s.group(2)),
                 "unverifiable": int(s.group(3)), "unknown": int(s.group(4))}
    return {"passed": passed, "failed": failed, "untested": untested, "split": split}


def judge(counts: dict, ratchet: dict) -> tuple[list[str], list[str]]:
    """返回 (reds, notes)。全过时 reds 为空。"""
    reds: list[str] = []
    notes: list[str] = []

    floor = ratchet.get("passed_floor")
    if not isinstance(floor, int):
        raise Untested("地板文件里没有整数 `passed_floor`")

    total = counts["passed"] + counts["failed"] + counts["untested"]

    # ① 不许有红的验收项
    if counts["failed"]:
        reds.append(f"failed={counts['failed']} —— 有红的验收项，一条都不许合入")

    # ② 总数必须对（防「删了几行所以看起来没倒退」）
    if total != TOTAL_ROWS:
        reds.append(f"计数之和 = {total}，不等于验收表总行数 {TOTAL_ROWS}"
                    f" —— 有人增删了行，或执行器少读/多读了行")

    # ③ 棘轮：passed 不许低于地板
    if counts["passed"] < floor:
        reds.append(f"passed={counts['passed']} **低于地板 {floor}** —— 棘轮倒退"
                    f"（{floor - counts['passed']} 条从 passed 掉了出去）")
    elif counts["passed"] > floor:
        notes.append(f"passed={counts['passed']} 已高于地板 {floor} —— "
                     f"**请手动把 tools/acceptance-ratchet.json 的 passed_floor 上调到 "
                     f"{counts['passed']}**，否则这段余量会掩盖下一次倒退")

    # ④ 分账之和必须等于 untested（分账自己也得自洽）
    if counts["split"] is not None:
        s = sum(counts["split"].values())
        if s != counts["untested"]:
            reds.append(f"untested_split 之和 = {s}，不等于 untested={counts['untested']}"
                        f" —— 分账自己不自洽")
        if counts["split"].get("unknown"):
            reds.append(f"untested_split 里有 {counts['split']['unknown']} 条记不出可验性"
                        f" —— 那几行读不出，不是「没问题」")
    else:
        reds.append("输出里没有 `untested_split:` 行 —— 无法区分「该写 verifier」"
                    "与「按人工验收」，两者下一步动作相反")

    return reds, notes


def run_runner() -> str:
    r = subprocess.run([sys.executable, str(RUNNER)],
                       capture_output=True, text=True, timeout=1800)
    return (r.stdout or "") + "\n" + (r.stderr or "")


# ─────────────────────────── 反向对照 ───────────────────────────


def _synthetic(passed: int, failed: int, untested: int,
               machine: int | None = None, manual: int | None = None) -> str:
    if machine is None:
        machine, manual = untested, 0
    return ("UNTESTED #1 fake 缺 test_id/fixture/command\n"
            "mapped=%d\n"
            "passed=%d failed=%d untested=%d\n"
            "untested_split: machine=%d manual=%d unverifiable=0 unknown=0\n"
            % (passed + failed, passed, failed, untested, machine, manual))


def run_controls() -> int:
    print("=" * 72)
    print("验收棘轮 · 反向对照（离线；只喂内存里的合成读数）")
    print("=" * 72)
    results: list[tuple[str, bool, str]] = []

    def ok(name, cond, detail=""):
        results.append((name, bool(cond), detail))
        print(f"  {'✅' if cond else '❌'} {name}" + (f"  {detail}" if not cond else ""))

    ratchet = {"passed_floor": 116}

    # 1 正样本：恰好等于地板
    reds, _ = judge(parse_counts(_synthetic(116, 0, 20, 13, 7)), ratchet)
    ok("正样本：passed=116 failed=0 untested=20 → 必须绿", not reds, repr(reds))

    # 2 ★ 有红 → 必须红（哪怕 passed 远超地板）
    reds, _ = judge(parse_counts(_synthetic(116, 1, 19, 12, 7)), ratchet)
    ok("★ 坏样本：failed=1（passed 仍 ≥ 地板）→ 必须红",
       any("failed=" in r for r in reds), repr(reds))

    # 3 ★ 棘轮倒退 → 必须红
    reds, _ = judge(parse_counts(_synthetic(115, 0, 21, 14, 7)), ratchet)
    ok("★ 坏样本：passed=115 < 地板 116 → 必须红（棘轮倒退）",
       any("低于地板" in r for r in reds), repr(reds))

    # 4 ★ 删行 → 必须红（这条是最容易漏的：passed 没倒退，failed 也是 0）
    _cut = ("mapped=116\n"
            "passed=116 failed=0 untested=15\n"
            "untested_split: machine=8 manual=7 unverifiable=0 unknown=0\n")
    reds, _ = judge(parse_counts(_cut), ratchet)
    ok("★ 坏样本：表被删了 5 行（passed 仍=116、failed=0）→ 必须红（总数不对）",
       any("总行数" in r for r in reds), repr(reds))

    # 5 ★ 分账自己不自洽 → 必须红
    _bad_split = ("passed=116 failed=0 untested=20\n"
                  "untested_split: machine=5 manual=7 unverifiable=0 unknown=0\n")
    reds, _ = judge(parse_counts(_bad_split), ratchet)
    ok("★ 坏样本：分账之和 ≠ untested → 必须红",
       any("分账" in r for r in reds), repr(reds))

    # 6 ★ 没有分账行 → 必须红（否则「该写 verifier」与「按人工验收」分不开）
    _no_split = "passed=116 failed=0 untested=20\n"
    reds, _ = judge(parse_counts(_no_split), ratchet)
    ok("★ 坏样本：没有 untested_split 行 → 必须红",
       any("untested_split" in r for r in reds), repr(reds))

    # 7 解析不出 → 未测（不是通过，也不是红）
    try:
        parse_counts("完全不是执行器的输出")
        ok("坏样本：解析不出 → 必须抛 Untested", False, "没有抛")
    except Untested:
        ok("坏样本：解析不出 → 必须抛 Untested（退 2，不是通过）", True)

    # 8 高于地板 → 绿，但必须**提醒上调**（否则余量会掩盖下一次倒退）
    reds, notes = judge(parse_counts(_synthetic(118, 0, 18, 11, 7)), ratchet)
    ok("高于地板：passed=118 → 绿，但必须提醒上调地板",
       not reds and any("上调" in n for n in notes), repr(notes))

    # 9 地板文件缺字段 → 未测
    try:
        judge(parse_counts(_synthetic(116, 0, 20, 13, 7)), {})
        ok("坏样本：地板文件无 passed_floor → 必须抛 Untested", False, "没有抛")
    except Untested:
        ok("坏样本：地板文件无 passed_floor → 必须抛 Untested", True)

    bad = [r for r in results if not r[1]]
    print("-" * 72)
    if bad:
        print(f"❌ {len(bad)}/{len(results)} 项不符")
        for n, _, d in bad:
            print(f"   {n}  {d}")
        return 1
    print(f"✅ {len(results)}/{len(results)} 项反向对照全过"
          f"（该绿、该红、该未测三侧都在）")
    return 0


# ─────────────────────────── 主 ───────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true",
                    help="自己跑一次验收执行器（默认从 stdin 读）")
    ap.add_argument("--controls", action="store_true")
    args = ap.parse_args()

    if args.controls:
        return run_controls()

    try:
        ratchet = json.loads(RATCHET.read_text(encoding="utf-8"))
    except Exception as exc:                                    # noqa: BLE001
        print(f"UNTESTED: 地板文件读不出：{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print("=" * 72)
    print("T-145 · 验收棘轮（failed=0 · 总数对 · passed 不倒退）")
    print("=" * 72)

    try:
        text = run_runner() if args.run else sys.stdin.read()
        counts = parse_counts(text)
    except Untested as exc:
        print(f"⚠ 未测：{exc} —— **不是通过**")
        return 2

    reds, notes = judge(counts, ratchet)
    split = counts["split"] or {}
    print(f"  passed={counts['passed']} failed={counts['failed']} "
          f"untested={counts['untested']}"
          + (f"（machine={split.get('machine')} manual={split.get('manual')}）"
             if split else ""))
    print(f"  地板 passed_floor = {ratchet['passed_floor']}"
          f"（记录于 {ratchet.get('recorded_at') or '未记'}）")
    print()
    for n in notes:
        print(f"  ⚠ {n}")
    for r in reds:
        print(f"  ❌ {r}")
    print("-" * 72)
    if reds:
        print(f"❌ 退 1：{len(reds)} 项红")
        return 1
    print("✅ 退 0：棘轮成立（failed=0、总数对、passed 未倒退）。")
    print("   ★ 不判 CI 是否真的在跑；也不判那 7 条 manual 有没有人工验收过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
