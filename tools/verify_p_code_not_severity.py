#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_p_code_not_severity.py —— 行 42：P 代号不得表达严重度

## 行 42 要什么

扫**报告模板 / 群消息模板 / 指标定义 / 验收表本身**：出现「P0 高危」「P0 严重」
「最高危 P0」等把 P 当严重度的表述即红；喂一个坏样本证明会红；
同时「P0 层 / 正则层」这类**检测层**用法必须不被误报。

## 为什么这条的反向对照是「不许误报」

全仓 `P0` 有大量合法用法（`DP0` 是处置层编号；「P0 层/正则层」是检测层）。
一个把所有 `P0` 都拦下的扫描器，会把它们全打成红 —— 那比没有更糟。
本脚本只认「P + 严重度词」的**组合**，并用两条正反样本把边界钉住：

* 坏样本：`P0 高危` / `最高危 P0` / `P1 严重` → 必须命中；
* 好样本：`P0 层` / `DP0` / `正则层` / `P0 规则集` → 必须不命中。

## 扫描对象的例外（明写）

验收表**第 42 行本身**要写出这三个坏样本（「出现『P0 高危』…即红」），
所以那一行必须排除，否则扫描器会把「定义规则的那句话」当成违规。
排除条件：行首是 `| 42 |`。这是本脚本唯一的知识性例外，写在代码里可复核。

退出码：0 / 1 / 2（目标文件读不出）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGETS = (
    ROOT / "tools" / "audit" / "report_render.mjs",   # 报告模板
    ROOT / "tools" / "reply-cards" / "contract.md",   # 群消息模板白名单
    ROOT / "base" / "metrics_read_model.py",          # 指标定义
    ROOT / "PMO" / "audit" / "验收表-v3-覆盖全部判据-20261017.md",
)

#: 「P 当严重度」的两种语序。前面不能紧跟字母（排除 DP0）。
PAT_AFTER = re.compile(r"(?<![A-Za-z])P[0-3]\s*(?:级)?\s*(?:高危|严重|最高危)")
PAT_BEFORE = re.compile(r"最高危\s*P[0-3](?![0-9])")


class Untested(Exception):
    pass


def is_exempt(line: str) -> bool:
    """验收表第 42 行本身要写出坏样本，必须排除。"""
    return line.strip().startswith("| 42 ")


def scan_text(text: str, *, exempt=None) -> list[tuple[int, str]]:
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        if exempt and exempt(line):
            continue
        if PAT_AFTER.search(line) or PAT_BEFORE.search(line):
            hits.append((i, line.strip()[:100]))
    return hits


def scan_all(targets=TARGETS) -> tuple[list[str], list[str]]:
    """返回 (问题, 读不到的文件)。"""
    problems, missing = [], []
    for p in targets:
        if not p.is_file():
            missing.append(str(p.relative_to(ROOT)))
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            missing.append(str(p.relative_to(ROOT)))
            continue
        for line_no, snippet in scan_text(text, exempt=is_exempt):
            problems.append(f"{p.relative_to(ROOT)}:{line_no} 把 P 当严重度：{snippet!r}")
    return problems, missing


def controls() -> int:
    bad = [
        "P0 高危：立即下线",
        "这是最高危 P0 问题",
        "P1 严重违规",
    ]
    good = [
        "P0 层（正则/关键词）不进入语义判定",
        "DP0 是处置层编号，不是严重度",
        "正则层命中 → P0 规则集",
        "P0 规则只含正则/关键词",
    ]
    cases = [
        ("反向对照：P0 层 / DP0 / 正则层 不得误报",
         lambda: all(not scan_text(t) for t in good)),
        ("★ 坏样本：P0 高危 → 必须命中", lambda: bool(scan_text(bad[0]))),
        ("★ 坏样本：最高危 P0 → 必须命中", lambda: bool(scan_text(bad[1]))),
        ("★ 坏样本：P1 严重 → 必须命中", lambda: bool(scan_text(bad[2]))),
        ("验收表第 42 行本身写出的坏样本 → 必须被排除（否则规则定义自己违规）",
         lambda: not scan_text("| 42 | 出现「P0 高危」「最高危 P0」即红 |", exempt=is_exempt)),
    ]
    fail = 0
    print("=" * 78)
    print("行 42 · P 代号不得表达严重度（离线对照）")
    print("=" * 78)
    for i, (name, fn) in enumerate(cases, 1):
        try:
            ok, err = bool(fn()), ""
        except Exception as e:  # noqa: BLE001
            ok, err = False, f"（{type(e).__name__}: {e}）"
        if not ok:
            fail += 1
        print(f"  {'✅' if ok else '❌'} [{i}/{len(cases)}] {name}{err}")
    print("-" * 78)
    if fail:
        print(f"❌ {len(cases)} 项中 {fail} 项失败")
        return 1
    print(f"✅ {len(cases)} 项全过（该红、该绿都有）")
    return 0


def main(argv: list[str]) -> int:
    if "--controls" in argv:
        return controls()
    problems, missing = scan_all()
    if len(missing) == len(TARGETS):
        print("⚠️ 未测：四个扫描对象一个都读不到")
        return 2
    print("=" * 78)
    print("行 42 · P 代号不得表达严重度")
    print("=" * 78)
    for p in TARGETS:
        rel = p.relative_to(ROOT)
        print(f"  · {rel} {'（不在盘上）' if not p.is_file() else ''}")
    if problems:
        for p in problems:
            print(f"  ❌ {p}")
        print(f"\n❌ 退 1：{len(problems)} 处把 P 当严重度")
        return 1
    print("✅ 退 0：报告模板 / 群消息模板 / 指标定义 / 验收表都没有「P+严重度词」的表述。")
    if missing:
        print(f"   ⚠️ 有 {len(missing)} 个对象读不到：{missing} —— 这一部分**未测**，不是通过。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ 未测：{type(exc).__name__}: {exc}")
        sys.exit(2)
