#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_ui_coverage_label.py —— 前端能不能读到 IR 的 `label`

## 为什么要有这个文件（T-120c 追加）

T-120b 修好了上游：IR 的 `not_evaluated_reason` 现在带
`{"what": "场景控制", "why": "no_control_points", "label": "未做·无控制点"}`。
但产品有**两个**读它的地方：

1. 报告渲染（`tools/audit/report_render.mjs`）—— 由 `verify_report_coverage_reason.py` 守着；
2. 前端案件详情（`web/src/api/client.ts` 的类型 + `web/src/pages/CaseDetailPage.tsx` 的渲染）。

第 2 条有两层独立的丢失：
* **类型层**：`interface NotEvaluated { what?; why? }` 没有 `label`，TypeScript 不许组件读它；
* **渲染层**：组件按 `WHY_TEXT[it.why]` 查表，等于让前端自己维护第二份措辞。

所以即使 IR 带了 label，界面也读不到 —— 这就跟 T-120b 之前「报告说成没接线」是同一个病，
只是换了一层。

## 断言（**源码级**，明着留的局限）

| 段 | 断言 |
|---|---|
| U1 | `client.ts` 的 `NotEvaluated` 声明了 `label` |
| U2 | `CaseDetailPage.tsx` 渲染理由时**读 label**（不是只查 `WHY_TEXT[why]`） |
| U3 | `WHY_TEXT` 仍有 `no_control_points` 的独立文案（与 `not_wired` 不同句） |

⚠️ **这里没有浏览器**：U1–U3 读的是源码文本，**不证明**真机上渲染成了什么。
要行为级，得等 `web/` 那批改动合进来后用 `agent-browser` 跑一次真实页面；
在那之前本节只能算「接口形状对上了」，不算「界面显示对了」。

## 归属

`web/` 是 ea 正在改的文件（有未提交改动）。本脚本**只测量、不改动**；
今天它红着是**真实状态**，不是误报。

退出码：全过 **0** ／ 有红 **1** ／ 文件读不出 **2**。

复现：
    python3 tools/verify_ui_coverage_label.py
    python3 tools/verify_ui_coverage_label.py --controls
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIENT = ROOT / "web" / "src" / "api" / "client.ts"
CASE_PAGE = ROOT / "web" / "src" / "pages" / "CaseDetailPage.tsx"

EMPTY_WHY = "no_control_points"


class Untested(Exception):
    pass


def read(path: Path) -> str:
    if not path.is_file():
        raise Untested(f"没有这个文件：{path}")
    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        raise Untested(f"{path} 读不出：{e}")


def not_evaluated_block(src: str) -> str:
    m = re.search(r"interface\s+NotEvaluated\s*\{(.*?)\}", src, re.S)
    return m.group(1) if m else ""


def check_client(src: str) -> list[str]:
    """U1：类型层必须声明 label。"""
    block = not_evaluated_block(src)
    if not block:
        return ["U1 client.ts 里找不到 `interface NotEvaluated` —— 口径变了，本判据失效"]
    if not re.search(r"\blabel\s*\??\s*:", block):
        return ["U1 `interface NotEvaluated` 没有声明 `label` —— TypeScript 不许组件读它，"
                "IR 带了的可读措辞到不了界面"]
    return []


def reason_line(src: str) -> str:
    """找到渲染「未跑的为什么」的那一行。"""
    for line in src.splitlines():
        if "WHY_TEXT" in line and "it.why" in line:
            return line.strip()
    return ""


def check_case_page(src: str) -> list[str]:
    """U2 / U3：渲染必须读 label，且空族有独立文案。"""
    problems = []
    line = reason_line(src)
    if not line:
        problems.append("U2 CaseDetailPage.tsx 里找不到按 `WHY_TEXT[...it.why]` 渲染的那一行 ——"
                        " 口径可能变了，本判据需要更新")
    elif "label" not in line:
        problems.append(
            "U2 渲染理由的表达式里没有 `label`（当前：" + line[:80] + "）——"
            " 界面用的是前端自己那份 WHY_TEXT，不是 IR 里的措辞")

    m = re.search(r"const\s+WHY_TEXT[^=]*=\s*\{(.*?)\};", src, re.S)
    if not m:
        problems.append("U3 找不到 WHY_TEXT 映射")
    else:
        body = m.group(1)
        if not re.search(rf"\b{EMPTY_WHY}\s*:", body):
            problems.append(f"U3 WHY_TEXT 没有 {EMPTY_WHY} 的文案")
        else:
            vm = re.search(rf"\b{EMPTY_WHY}\s*:\s*\"([^\"]*)\"", body)
            nm = re.search(r'\bnot_wired\s*:\s*"([^"]*)"', body)
            if vm and nm and vm.group(1) == nm.group(1):
                problems.append("U3 空族与 not_wired 共用同一句文案 —— 两个缺口又被混成一件事")
    return problems


def assess(client_src: str, page_src: str) -> list[str]:
    return check_client(client_src) + check_case_page(page_src)


def controls() -> int:
    client_ok = "export interface NotEvaluated {\n  what?: string | null;\n  why?: string | null;\n  label?: string | null;\n}\n"
    client_bad = "export interface NotEvaluated {\n  what?: string | null;\n  why?: string | null;\n}\n"
    page_ok = ('const WHY_TEXT: Record<string, string> = {\n'
               '  not_wired: "未接线（根本没跑，不是跑了没问题）",\n'
               '  no_control_points: "未做·无控制点（这一族还没有定控制点）",\n'
               '};\n'
               '  <span>{it.label ?? WHY_TEXT[String(it.why)] ?? String(it.why ?? "未说明")}</span>\n')
    page_no_label = ('const WHY_TEXT: Record<string, string> = {\n'
                     '  not_wired: "未接线（根本没跑，不是跑了没问题）",\n'
                     '  no_control_points: "未做·无控制点（这一族还没有定控制点）",\n'
                     '};\n'
                     '  <span>{WHY_TEXT[String(it.why)] ?? String(it.why ?? "未说明")}</span>\n')
    page_shared = ('const WHY_TEXT: Record<string, string> = {\n'
                   '  not_wired: "未接线（根本没跑，不是跑了没问题）",\n'
                   '  no_control_points: "未接线（根本没跑，不是跑了没问题）",\n'
                   '};\n'
                   '  <span>{it.label ?? WHY_TEXT[String(it.why)]}</span>\n')

    def red(i, c=client_ok, p=page_ok):
        return any(i in x for x in assess(c, p))

    cases = [
        ("正样本：类型有 label + 渲染读 label → 必须绿", lambda: not assess(client_ok, page_ok)),
        ("★ U1 坏样本：interface NotEvaluated 缺 label → 必须红", lambda: red("U1", c=client_bad)),
        ("★ U2 坏样本：渲染不读 label（只查 WHY_TEXT）→ 必须红", lambda: red("U2", p=page_no_label)),
        ("★ U3 坏样本：空族与 not_wired 共用一句 → 必须红", lambda: red("U3", p=page_shared)),
        ("U3 坏样本：WHY_TEXT 缺空族文案 → 必须红",
         lambda: red("U3", p=page_ok.replace('  no_control_points: "未做·无控制点（这一族还没有定控制点）",\n', ""))),
        ("U1 坏样本：连 interface 都找不到 → 必须红", lambda: red("U1", c="const x = 1;\n")),
    ]

    bad = 0
    print("=" * 78)
    print("前端能不能读到 IR 的 label · 反向对照（源码级；不启动浏览器）")
    print("=" * 78)
    for i, (name, fn) in enumerate(cases, 1):
        try:
            ok, err = bool(fn()), ""
        except Exception as e:  # noqa: BLE001
            ok, err = False, f"（抛异常 {type(e).__name__}: {e}）"
        if not ok:
            bad += 1
        print(f"  {'✅' if ok else '❌'} [{i}/{len(cases)}] {name}{err}")
    print("-" * 78)
    if bad:
        print(f"❌ {len(cases)} 项中 {bad} 项失败 —— 判据有问题，别信它")
        return 1
    print(f"✅ {len(cases)} 项全过")
    return 0


def main(argv: list[str]) -> int:
    if "--controls" in argv:
        return controls()

    try:
        client_src = read(CLIENT)
        page_src = read(CASE_PAGE)
    except Untested as e:
        print(f"⚠️ 未测：{e}")
        return 2

    problems = assess(client_src, page_src)

    print("=" * 78)
    print("前端能不能读到 IR 的 label（**源码级**；不启动浏览器）")
    print("=" * 78)
    print(f"  NotEvaluated = {{{not_evaluated_block(client_src).strip()[:120]}}}")
    print(f"  渲染表达式：{reason_line(page_src)[:120]}")
    print()
    if problems:
        print(f"── 有问题 {len(problems)} 处 ──")
        for p in problems:
            print(f"  ❌ {p}")
        print()
        print(f"❌ 退 1：{len(problems)} 处不成立（**web/ 归 ea；本脚本只测量，不改动**）")
        return 1
    print("✅ 退 0：类型层声明了 label，渲染层读的是 label（不是前端自造的第二份措辞）。")
    print("   ⚠️ 源码级断言：不证明真机渲染结果。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ 未测：验收器自身异常：{type(exc).__name__}: {exc}")
        sys.exit(2)
