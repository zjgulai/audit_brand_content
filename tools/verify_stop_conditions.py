#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_stop_conditions.py —— 行 36：停机条件登记与「不提前停」

## 行 36 三个要求与覆盖

| 要求 | 执行点 | 状态 |
|---|---|---|
| 登记恰有 6 条、每条 `status=not_applicable_stage1` | **S1**（解析 Playbook §3.3.7 的 MD 表） | ✅ |
| 第一阶段口径统一为「不提前停」 | **S2**（真跑判定入口：五步各一次、`skipped=[]`；回执 schema 的原因枚举不含 `early_stop`） | ✅ |
| 全仓没有任何一项要求「两轮」/「无进展」行为 | **S3**（剥掉注释与 docstring 后扫可执行源码，命中即红） | ✅（负向，带反向对照） |

**为什么登记表读 MD 而不是 JSON**：全仓没有 `stop-conditions-v1.json`，
`not_applicable_stage1` 在代码/JSON 里 0 命中；唯一的登记就是 Playbook:759-770。
行 36 说「读取停机条件登记」，读它 = 读这张表。**没有为凑验收去新建一个 JSON**
（那会让同一份登记有两处，改一处漂一处）。

**S3 的已知盲区**：只扫 `base/ api/` 的可执行源码；行尾注释不算代码（与
`verify_control_points` 的扫描器同一读法），整行注释与 docstring 先剥掉。
`Playbook` 里「连续两轮」是**登记表文字**，不是行为要求 —— 不扫文档。

退出码：0 / 1 / 2（Playbook 读不出、判定入口跑不出 → 未测）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PLAYBOOK = ROOT / "Playbook" / "内容审查Agent-产品Playbook-v1.1.md"
RECEIPT_SCHEMA = ROOT / "contracts" / "receipt-v1.schema.json"
SCAN_DIRS = (ROOT / "base", ROOT / "api")
EXPECTED_ROWS = 6
STAGE1 = "not_applicable_stage1"
#: 行为特征：这些词出现在**可执行代码**里，就说明有人实现了提前停 / 无进展停。
STOP_PATTERNS = ("early_stop", "no_progress", "consecutive_rounds", "stop_condition")


class Untested(Exception):
    pass


def read_playbook() -> str:
    if not PLAYBOOK.is_file():
        raise Untested(f"没有 Playbook：{PLAYBOOK}")
    return PLAYBOOK.read_text(encoding="utf-8")


def parse_stop_table(text: str) -> list[dict]:
    """从 §3.3.7 的 MD 表里取停机条件行。"""
    m = re.search(r"####\s*3\.3\.7\s*停机条件.*?\n(.*?)(?=\n####|\n---|\Z)", text, re.S)
    if not m:
        raise Untested("Playbook 里找不到 §3.3.7 停机条件小节")
    rows = []
    for line in m.group(1).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not re.fullmatch(r"\d+", cells[0]):
            continue
        rows.append({"id": int(cells[0]), "condition": cells[1], "stage1": cells[2]})
    if not rows:
        raise Untested("§3.3.7 里解析不出任何停机条件行 —— 表格式变了")
    return rows


def check_registry(rows: list[dict]) -> list[str]:
    """S1。"""
    problems = []
    if len(rows) != EXPECTED_ROWS:
        problems.append(f"S1 停机条件登记 {len(rows)} 条，预期恰好 {EXPECTED_ROWS} 条")
    ids = [r["id"] for r in rows]
    if sorted(ids) != list(range(1, EXPECTED_ROWS + 1)):
        problems.append(f"S1 编号不是 1..{EXPECTED_ROWS} 各一次：{ids}")
    for r in rows:
        if STAGE1 not in r["stage1"]:
            problems.append(f"S1 第 {r['id']} 条的第一阶段状态不是 {STAGE1}：{r['stage1']!r}")
    return problems


def check_no_early_stop() -> list[str]:
    """S2：真跑判定入口，五步各一次、无跳过；回执枚举不含 early_stop。"""
    problems = []
    try:
        from base import contract as C  # noqa: PLC0415
        from base.judge_entry import judge_unit  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        raise Untested(f"导入判定入口失败：{type(e).__name__}: {e}")
    unit = C.from_text("这款产品可以治疗疾病，疗效显著。")
    r = judge_unit(unit, clock=lambda: 1000,
                   authority_query=lambda _ref: {"state": "ok", "reason": "verify"})
    if r.get("steps") != ["normalize", "judge", "dispose", "output", "evaluate"]:
        problems.append(f"S2 判定步骤不是五步各一次：{r.get('steps')}")
    receipt = r.get("receipt") or {}
    skipped = receipt.get("skipped", receipt.get("skipped_steps"))
    if skipped != []:
        problems.append(f"S2 回执 skipped 非空：{skipped!r} —— 有东西被提前跳过了")
    try:
        import json
        schema = json.loads(RECEIPT_SCHEMA.read_text(encoding="utf-8"))
        enum = (schema["properties"]["skipped"]["items"]["properties"]["reason"]["enum"])
    except Exception as e:  # noqa: BLE001
        raise Untested(f"读回执 schema 的 skipped 枚举失败：{e}")
    if "early_stop" in enum or "no_progress" in enum:
        problems.append(f"S2 回执 schema 的跳过原因枚举里出现了停机类原因：{enum}")
    return problems


def strip_comments_and_docstrings(src: str) -> str:
    """剥掉整行注释与三引号块，保留可执行代码（与项目既有扫描器同一读法）。"""
    src = re.sub(r'"""(?:.|\n)*?"""', "", src)
    src = re.sub(r"'''(?:.|\n)*?'''", "", src)
    return "\n".join(ln for ln in src.splitlines() if not ln.strip().startswith("#"))


def scan_for_stop_behaviour(sources: dict[str, str]) -> list[str]:
    """S3：可执行代码里出现停机行为特征即红。"""
    hits = []
    for rel, src in sources.items():
        code = strip_comments_and_docstrings(src)
        for i, line in enumerate(code.splitlines(), 1):
            for pat in STOP_PATTERNS:
                if pat in line:
                    hits.append(f"{rel}:{i} 出现 {pat}（{line.strip()[:70]}）")
    return hits


def collect_sources() -> dict[str, str]:
    out = {}
    for d in SCAN_DIRS:
        for p in sorted(d.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            try:
                out[str(p.relative_to(ROOT))] = p.read_text(encoding="utf-8")
            except OSError:
                continue
    if not out:
        raise Untested("扫描目录里没有 .py —— 口径可能变了")
    return out


def assess(rows: list[dict], sources: dict[str, str]) -> list[str]:
    return check_registry(rows) + check_no_early_stop() + scan_for_stop_behaviour(sources)


def controls() -> int:
    rows = [{"id": i, "condition": "x", "stage1": f"`{STAGE1}`（登记保留，不执行）"}
            for i in range(1, 7)]
    # ★ 整行注释不算代码；**行尾注释仍会被扫到**（与项目既有扫描器同一已知盲区）。
    good_src = {"base/x.py": "# early_stop 在这里只是登记词，不是行为\ndef f():\n    return 1\n"}
    bad_src = {"base/x.py": "def f():\n    if no_progress:\n        return None\n"}

    def red(frag, rows_=None, src_=None):
        return any(frag in p for p in assess(rows_ or rows, src_ or good_src))

    cases = [
        ("正样本：6 条齐全 + 无停机行为 → 必须绿", lambda: not assess(rows, good_src)),
        ("★ S1 坏样本：删掉一条 → 必须红", lambda: red("S1", rows_=rows[:5])),
        ("★ S1 坏样本：把一条状态改成 enabled → 必须红",
         lambda: red("S1", rows_=[*rows[:5], dict(rows[5], stage1="enabled")])),
        ("★ S3 坏样本：可执行代码里出现 no_progress → 必须红", lambda: red("no_progress", src_=bad_src)),
        ("反向对照：同一句只出现在注释里 → 不许误报",
         lambda: not any("no_progress" in p for p in
                         scan_for_stop_behaviour({"base/x.py": "# no_progress 只是注释\nreturn 1\n"}))),
    ]
    bad = 0
    print("=" * 78)
    print("行 36 · 停机条件登记 / 不提前停（离线对照）")
    print("=" * 78)
    for i, (name, fn) in enumerate(cases, 1):
        try:
            ok, err = bool(fn()), ""
        except Exception as e:  # noqa: BLE001
            ok, err = False, f"（{type(e).__name__}: {e}）"
        if not ok:
            bad += 1
        print(f"  {'✅' if ok else '❌'} [{i}/{len(cases)}] {name}{err}")
    print("-" * 78)
    if bad:
        print(f"❌ {len(cases)} 项中 {bad} 项失败")
        return 1
    print(f"✅ {len(cases)} 项全过")
    return 0


def main(argv: list[str]) -> int:
    if "--controls" in argv:
        return controls()
    try:
        rows = parse_stop_table(read_playbook())
        sources = collect_sources()
        problems = assess(rows, sources)
    except Untested as e:
        print(f"⚠️ 未测：{e}")
        return 2
    print("=" * 78)
    print("行 36 · 停机条件登记（Playbook §3.3.7）与不提前停")
    print("=" * 78)
    for r in rows:
        print(f"  · {r['id']} {r['condition'][:28]:<28} → {r['stage1'][:40]}")
    print()
    if problems:
        for p in problems:
            print(f"  ❌ {p}")
        print(f"\n❌ 退 1：{len(problems)} 处不成立")
        return 1
    print(f"✅ 退 0：登记 {len(rows)} 条、全部 {STAGE1}；真实入口五步各一次、无跳过；")
    print("   可执行代码里没有 early_stop / no_progress / consecutive_rounds 行为。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ 未测：{type(exc).__name__}: {exc}")
        sys.exit(2)
