#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_acceptance_index.py —— 判据 ↔ 验收项 的机器对拍

存在的理由：验收表上写「347/347 全被覆盖」—— 这是一句**声称**，不是读数。
本脚本把它变成读数：从文档抽判据编号，从验收表抽覆盖列，双向比对，指出缺失。

两个口径必须分开报，不许混：
  ① **编号判据**（文档里加粗的 L1-x / V1 / C1 / I1 / MC-1 …）—— 这是硬指标
  ② **散落要求**（用「必须/不许/一律/永不」但无编号的句子）—— 这是辅助，靠 SEC-* 临时编号

★ 上一版把 ② 混进 ① 一起报成「347 条」，读起来像「文档有 347 个判据」——
  那是错的。① 只有 82 条。

用法：
  python3 tools/verify_acceptance_index.py            # 默认对拍 v1.1 + v3 验收表
  python3 tools/verify_acceptance_index.py --json     # 机器可读

判据（退出码）：
  0  全部编号判据都被覆盖
  1  有编号判据没被覆盖
  2  文件读不到（未测，不是通过）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "Playbook" / "内容审查Agent-产品Playbook-v1.1.md"
TAB = ROOT / "PMO" / "audit" / "验收表-v3-覆盖全部判据-20261017.md"

# 编号判据的形态（加粗）。**刻意逐个点名，不用宽泛正则** ——
# 宽泛正则会把你正文里的岔引也抓进来（AGENTS.md §2.4.1 的假阳性教训）。
ID_PATTERN = re.compile(
    r"\*\*("
    r"L[1-6]-\d+[a-z]?"      # L1-0 / L1-0b / L2-6a
    r"|V[1-5]"
    r"|C[1-4]"
    r"|M[1-3]"
    r"|MSG-[1-4]"            # §4.3.2 群消息模板（2026-10-17 从撞号的 M1-M4 改名）
    r"|LOC-[1-4]"
    r"|I[1-7]"
    r"|R[1-3]"
    r"|F[1-2]"
    r"|MC-[1-3]"
    r"|RL-\d+"               # §4.4 放行门（2026-10-18 委托方定，15 条）
    r"|TS-\d+"               # §4.5 交付与界面约束（2026-10-18 委托方定，17 条）
    r")\*\*"
)

# 验收表 covered 列的编号（含 SEC-* 这类临时编号，单列一类）
COV_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]*\d[A-Za-z]?$")


def extract_doc_ids(text: str) -> set[str]:
    return {m.group(1) for m in ID_PATTERN.finditer(text)}


def extract_covered(text: str) -> tuple[set[str], set[str], dict[str, int]]:
    """返回 (编号判据覆盖集, SEC-* 临时编号集, verifiability 计数)"""
    real: set[str] = set()
    sec: set[str] = set()
    vcount: dict[str, int] = {"machine": 0, "manual": 0, "unverifiable": 0}
    for line in text.splitlines():
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 5:
            continue
        cov = cells[3]
        for token in re.split(r"[/、,，\s]+", cov):
            # 去掉括号后缀：验收表用「M1(§3.3.4.1)」区分同名判据
            token = re.sub(r"[（(].*?[)）]", "", token).strip()
            if not re.fullmatch(r"[A-Z][A-Za-z0-9.\-]*", token):
                continue
            if token.startswith("SEC-"):
                sec.add(token)
            else:
                real.add(token)
        # verifiability：行尾那一格
        for cell in reversed(cells):
            if cell in ("machine", "manual", "unverifiable"):
                vcount[cell] += 1
                break
    return real, sec, vcount


def count_table_rows(text: str) -> int:
    return len(re.findall(r"^\| \d+ \|", text, re.M))


def parse_header_claims(text: str) -> dict[str, int | None]:
    """从表头抽声称的数字，用于一致性断言。抽不到给 None。"""
    claims: dict[str, int | None] = {}
    m = re.search(r"\*\*验收项数\*\*\D*(\d+)", text)
    claims["rows"] = int(m.group(1)) if m else None
    m = re.search(r"可机验\D*(\d+)", text)
    claims["machine"] = int(m.group(1)) if m else None
    m = re.search(r"需人工\D*(\d+)", text)
    claims["manual"] = int(m.group(1)) if m else None
    m = re.search(r"写不出验法\D*(\d+)", text)
    claims["unverifiable"] = int(m.group(1)) if m else None
    return claims


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", default=str(DOC))
    ap.add_argument("--tab", default=str(TAB))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    doc_p, tab_p = Path(args.doc), Path(args.tab)
    for p in (doc_p, tab_p):
        if not p.exists():
            print(f"✗ 读不到 {p} —— 未测，不是通过", file=sys.stderr)
            return 2

    doc_text = doc_p.read_text(encoding="utf-8")
    tab_text = tab_p.read_text(encoding="utf-8")

    doc_ids = extract_doc_ids(doc_text)
    covered, sec_ids, vcount = extract_covered(tab_text)
    rows = count_table_rows(tab_text)
    claims = parse_header_claims(tab_text)

    missing = sorted(doc_ids - covered)
    unknown = sorted(covered - doc_ids)   # 验收表引用了但文档里没有的编号

    # 口径声明：unknown 是「验收动作的内部标签」，不是判据。
    # 硬口径 = 82 条文档编号判据全部被覆盖；辅助口径 = SEC-* 与内部标签，
    # 它们只要求**有定义来源**（来自枚举清单），不参与 rc。
    result = {
        "doc": str(doc_p.relative_to(ROOT)),
        "tab": str(tab_p.relative_to(ROOT)),
        "doc_id_count": len(doc_ids),
        "covered_id_count": len(covered & doc_ids),
        "missing": missing,
        "unknown_in_table": unknown,
        "sec_temp_ids": len(sec_ids),
        "rows": rows,
        "verifiability": vcount,
        "header_claims": claims,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        print("=" * 62)
        print("判据 ↔ 验收项 对拍")
        print("=" * 62)
        print(f"  文档编号判据      {len(doc_ids):>4} 条")
        print(f"  验收表已覆盖      {len(covered & doc_ids):>4} 条")
        print(f"  未被覆盖          {len(missing):>4} 条")
        print(f"  验收表引用但文档无   {len(unknown):>4} 条  ← 编号对不上")
        print(f"  SEC-* 临时编号       {len(sec_ids):>4} 个  ← 辅助口径，不计入上面的数")
        print(f"  验收项（编号行）      {rows:>4} 项")
        print(f"    可机验 / 需人工 / 写不出验法   {vcount['machine']} / {vcount['manual']} / {vcount['unverifiable']}")
        if missing:
            print("\n  未被覆盖的：")
            for m in missing:
                print(f"    - {m}")
        if unknown:
            print("\n  验收表里引用了、文档里没有的编号（前 20）：")
            for u in unknown[:20]:
                print(f"    - {u}")
            print("  说明：这些是验收动作的内部标签（如 DER-2=状态转换第2条），"
                  f"\n        不是文档判据。它们**不计入 {len(doc_ids)}**，但表头已声明这一口径。")

    # 头部数字 vs 实表（AGENTS.md §2.2 第 1 条：文档里的数字要算出来）
    mismatch = []
    actual = {
        "rows": rows,
        "machine": vcount["machine"],
        "manual": vcount["manual"],
        "unverifiable": vcount["unverifiable"],
    }
    for k, claimed in claims.items():
        if claimed is not None and claimed != actual[k]:
            mismatch.append(f"{k}: 头部写 {claimed}，实表 {actual[k]}")
    if mismatch:
        print("\n  ⚠ 头部数字与实表不一致：")
        for m in mismatch:
            print(f"    - {m}")
        result["header_mismatch"] = mismatch

    if missing:
        print(f"\n✗ 有 {len(missing)} 条编号判据没有验收项")
        return 1
    if mismatch:
        print(f"\n✗ 头部数字与实表不一致（{len(mismatch)} 处）—— 不许把声称当读数")
        return 1
    print(f"\n✅ 全部 {len(doc_ids)} 条编号判据都有验收项")
    return 0


if __name__ == "__main__":
    sys.exit(main())
