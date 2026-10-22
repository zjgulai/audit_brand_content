#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_report_coverage_reason.py —— 报告里读不读得到「未做·无控制点」

## 为什么要有这个文件（T-120c）

验收表 #72 的原话是「**再读一份报告**，断言其中出现这些族『无规则/无控制点』的说明」。
T-120b 只把这条修到了 **IR** 那一层：IR 里 now 有 `why=no_control_points` 与
`label=未做·无控制点`。**报告能不能把它渲染出来，此前从未被断言过。**

本脚本走**真实产出路径**：`judge_unit()` → ReviewIR → RenderSnapshot →
`tools/audit/report_render.mjs` 的 `renderReport()` → 读回 markdown。

## 断言

| 段 | 断言 |
|---|---|
| S1 | 报告渲染成功（`ok=true`，六区块在） |
| S2 | 「## 覆盖证明」段里，**每个空族逐族**出现「族名（未做·无控制点）」 |
| S3 | 报告正文里**不许出现原始枚举串** `no_control_points` —— 用户不该读到代码里的词 |
| S4 | **溯源**：报告里那句措辞必须来自 IR 的 `label`。把 `label` 从 IR 里拿掉后重渲染，句子必须降级 —— 若仍出现「未做·无控制点」，说明渲染器自己又造了一份映射（两个口径） |
| S5 | 降级后必须**看得出来**：原始 why 出现在报告里，而不是被静默说成「未说明」 |

## 反向对照（`--controls`）

* 报告里缺一个空族 → S2 红；出现原始枚举串 → S3 红；
* 把 label 拿掉后报告**仍**显示「未做·无控制点」→ S4 红（这是「渲染器自己有第二份映射」的形状）；
* 把 label 拿掉后报告变成「未说明」→ S5 红（把缺口藏起来）。

退出码：全过 **0** ／ 有红 **1** ／ 未测（node 不可用、渲染抛错、表读不出）**2**。

复现：
    python3 tools/verify_report_coverage_reason.py
    python3 tools/verify_report_coverage_reason.py --controls
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "base"), str(ROOT / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

CP_TABLE = ROOT / "research" / "governance" / "control-points-v1.json"
RENDERER = ROOT / "tools" / "audit" / "report_render.mjs"

EMPTY_LABEL = "未做·无控制点"
EMPTY_WHY = "no_control_points"
CLEAN_TEXT = "这款吸奶器采用食品级硅胶材质，容量 150ml。"
COVERAGE_TITLE = "## 覆盖证明"


class Untested(Exception):
    """读不出 / 渲染不出 —— 退 2，不许当成绿。"""


# ─────────────────────────── 读 ───────────────────────────


def empty_families() -> list[str]:
    if not CP_TABLE.is_file():
        raise Untested(f"没有控制点表：{CP_TABLE}")
    try:
        d = json.loads(CP_TABLE.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        raise Untested(f"{CP_TABLE} 读不出：{type(e).__name__}: {e}")
    fams = d.get("empty_families")
    if not isinstance(fams, list):
        raise Untested(f"{CP_TABLE} 缺 empty_families 数组")
    return [x.get("family") for x in fams if isinstance(x, dict) and x.get("family")]


def real_ir() -> dict:
    try:
        from base import contract as C  # noqa: PLC0415
        from base.judge_entry import judge_unit  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        raise Untested(f"导入判定入口失败：{type(e).__name__}: {e}")
    try:
        r = judge_unit(C.from_text(CLEAN_TEXT), clock=lambda: 1000)
    except Exception as e:  # noqa: BLE001
        raise Untested(f"真实入口跑不出：{type(e).__name__}: {e}")
    ir = r.get("ir")
    if not isinstance(ir, dict):
        raise Untested("判定结果里没有 IR")
    return ir


def build_snapshot(ir: dict) -> dict:
    """按 report_render 的 RenderSnapshot 形状组装（只喂它读得到的字段）。"""
    return {
        "report_url": "https://example.test/reports/verify.md",
        "ir": ir,
        "evidence": [],
        "unassessed": [],
        "receipt": {"skill": "content-review", "version": "1.0", "fingerprint": "rc-verify",
                    "skipped_steps": [], "rule_snapshot": "rs-verify"},
        "failure_kind_counts": {"fetch_error": 0, "parse_error": 0, "empty": 0, "unsupported": 0},
        "unknown_bucket_counts": {},
    }


def render(snapshot: dict) -> dict:
    """真的调 Node 渲染器（唯一报告产出路径）。"""
    if shutil.which("node") is None:
        raise Untested("node 不在 PATH 里 —— 无法调 tools/audit/report_render.mjs")
    if not RENDERER.is_file():
        raise Untested(f"没有渲染器：{RENDERER}")
    code = (
        "import {renderReport} from %r;"
        "let b='';for await (const c of process.stdin) b+=c;"
        "const r=renderReport(JSON.parse(b));"
        "process.stdout.write(JSON.stringify({ok:r.ok,errors:r.errors||[],markdown:r.markdown||''}));"
        % str(RENDERER)
    )
    try:
        p = subprocess.run(["node", "--input-type=module", "-e", code],
                           input=json.dumps(snapshot, ensure_ascii=False),
                           capture_output=True, text=True, timeout=60)
    except Exception as e:  # noqa: BLE001
        raise Untested(f"调渲染器失败：{type(e).__name__}: {e}")
    if p.returncode != 0:
        raise Untested(f"渲染器退出码 {p.returncode}：{(p.stderr or '')[:300]}")
    try:
        return json.loads(p.stdout)
    except Exception as e:  # noqa: BLE001
        raise Untested(f"渲染器输出不是 JSON：{type(e).__name__}: {e}")


def strip_labels(ir: dict) -> dict:
    """深拷贝 IR，并去掉每个 not_evaluated_reason 的 label（反向对照用）。"""
    clone = json.loads(json.dumps(ir, ensure_ascii=False))
    cov = clone.get("coverage") or {}
    for r in cov.get("not_evaluated_reason") or []:
        if isinstance(r, dict):
            r.pop("label", None)
    return clone


# ─────────────────────────── 判 ───────────────────────────


def coverage_block(md: str) -> str:
    i = md.find(COVERAGE_TITLE)
    if i < 0:
        return ""
    rest = md[i + len(COVERAGE_TITLE):]
    j = rest.find("\n## ")
    return rest if j < 0 else rest[:j]


def check_report(md: str, families: list[str]) -> list[str]:
    """S2 / S3：报告正文里逐族读得到，且不许漏枚举原词。"""
    problems = []
    block = coverage_block(md)
    if not block:
        return [f"S1 报告里找不到「{COVERAGE_TITLE}」段 —— 覆盖证明没渲染出来"]
    for fam in families:
        if f"{fam}（{EMPTY_LABEL}）" not in block:
            problems.append(
                f"S2 报告「覆盖证明」段里没有「{fam}（{EMPTY_LABEL}）」——"
                " 用户读不到这一族是「还没定控制点」")
    if EMPTY_WHY in md:
        problems.append(
            f"S3 报告正文里出现了原始枚举串 `{EMPTY_WHY}` —— 那是代码里的词，不是给用户看的")
    return problems


def check_traceability(md_with: str, md_without: str, families: list[str]) -> list[str]:
    """S4 / S5：报告措辞必须来自 IR 的 label；拿掉 label 后必须降级且看得见。"""
    problems = []
    block_without = coverage_block(md_without)
    if any(f"{fam}（{EMPTY_LABEL}）" in block_without for fam in families):
        problems.append(
            "S4 把 IR 里的 `label` 拿掉后，报告**仍然**显示「未做·无控制点」——"
            " 说明渲染器自己又维护了一份映射（两个口径），报告的措辞不是从 IR 来的")
    if EMPTY_WHY not in md_without:
        problems.append(
            f"S5 拿掉 label 后报告里既没有可读标签、也没有原始 why（`{EMPTY_WHY}`）——"
            " 缺口被静默说成了别的东西（例如「未说明」）")
    return problems


def assess(md: str, md_without: str, families: list[str]) -> list[str]:
    return check_report(md, families) + check_traceability(md, md_without, families)


# ─────────────────────────── 反向对照 ───────────────────────────


def controls() -> int:
    fams = ["场景控制", "权利控制", "渠道控制"]
    good = ("# 内容审查报告\n\n## 覆盖证明\n"
            + "；".join(f"{f}（{EMPTY_LABEL}）" for f in fams) + "\n\n## 依据清单\n无\n")
    degraded = ("# 内容审查报告\n\n## 覆盖证明\n"
                + "；".join(f"{f}（{EMPTY_WHY}）" for f in fams) + "\n\n## 依据清单\n无\n")

    def red(i, md=good, md2=degraded, families=fams):
        return any(i in p for p in assess(md, md2, families))

    cases = [
        ("正样本：有 label 的报告 + 降级后显原始 why → 必须绿",
         lambda: not assess(good, degraded, fams)),
        ("★ S2 坏样本：少了一个空族 → 必须红", lambda: red("S2", md=good.replace(f"；{fams[2]}（{EMPTY_LABEL}）", ""))),
        ("★ S3 坏样本：报告里出现原始枚举串 → 必须红", lambda: red("S3", md=good + "\n（no_control_points）\n")),
        ("S1 坏样本：没有「覆盖证明」段 → 必须红", lambda: red("S1", md="# 报告\n\n## 结论\nREVIEW\n")),
        ("★ S4 坏样本：拿掉 label 后报告仍显示「未做·无控制点」→ 必须红",
         lambda: red("S4", md2=good)),
        ("S5 坏样本：拿掉 label 后被说成「未说明」→ 必须红",
         lambda: red("S5", md2=good.replace(EMPTY_LABEL, "未说明"))),
        ("反向对照：降级后显示原始 why 时，S5 不该误报（上面那条不是恒红）",
         lambda: not any("S5" in p for p in assess(good, degraded, fams))),
    ]

    bad = 0
    print("=" * 78)
    print("报告里的「未做·无控制点」· 反向对照（离线；只喂内存文本）")
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
    print(f"✅ {len(cases)} 项全过（该红、该绿、以及「不许有第二份映射」都在）")
    return 0


# ─────────────────────────── 主 ───────────────────────────


def main(argv: list[str]) -> int:
    if "--controls" in argv:
        return controls()

    try:
        fams = empty_families()
        ir = real_ir()
        out = render(build_snapshot(ir))
        if not out.get("ok"):
            raise Untested(f"渲染器报错：{out.get('errors')}")
        md = out.get("markdown") or ""
        out2 = render(build_snapshot(strip_labels(ir)))
        if not out2.get("ok"):
            raise Untested(f"降级渲染报错：{out2.get('errors')}")
        md2 = out2.get("markdown") or ""
    except Untested as e:
        print(f"⚠️ 未测：{e}")
        print("   这不是「报告里读得到」，是**这次没测成** —— 退 2（未测 ≠ 通过 ≠ 红）。")
        return 2

    problems = assess(md, md2, fams)

    print("=" * 78)
    print("报告里读不读得到「未做·无控制点」")
    print("=" * 78)
    print(f"  空族（{len(fams)}）：{fams}")
    for line in coverage_block(md).strip().splitlines():
        if "未跑的为什么" in line:
            print(f"  报告：{line.strip()}")
    for line in coverage_block(md2).strip().splitlines():
        if "未跑的为什么" in line:
            print(f"  去掉 label 后：{line.strip()}")
    print()
    if problems:
        print(f"── 有问题 {len(problems)} 处 ──")
        for p in problems:
            print(f"  ❌ {p}")
        print()
        print(f"❌ 退 1：{len(problems)} 处不成立")
        return 1
    print("✅ 退 0：报告「覆盖证明」段逐族写着「未做·无控制点」，")
    print("   措辞来自 IR 的 label（拿掉 label 会降级成原始 why，说明没有第二份映射）。")
    print()
    print("   ⚠️ 这句只覆盖**报告渲染**这一层：#72 原文的「读一份报告」到此为止；")
    print("      前端 CaseDetail 那侧读不读 label 是另一层（见 verify_ui_coverage_label.py）。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ 未测：验收器自身异常：{type(exc).__name__}: {exc}")
        sys.exit(2)
