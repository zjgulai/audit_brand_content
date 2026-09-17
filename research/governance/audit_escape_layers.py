#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_escape_layers.py — 转义层审计

背景：本项目的数据以 Markdown 表格形式存储，单元格内的 `|` 必须写成 `\\|`。
这引入了一个**两层转义**问题：

    Markdown 层：`|` → `\\|`（保护表格结构）
    数据层：    `\\|` → `|`（还原为内容）

任何读取这份数据的解析器，都必须把两层分清。本脚本检查：
  1. 规则表 21 行、记录表 291 行，在正确的转义感知切分下字段数是否完整
  2. 规则的正则字段在**还原后**是否真的有效（而不是把 `\\|` 当成字面竖线）
  3. 「未做还原」会造成多大的诊断偏差

这个脚本存在的理由是一次真实的方法错误：本项目在诊断过程中
**两次**因为没做还原而得出错误结论（详见 05-内部证据-转义层与解析陷阱.md）。

只读 PRD/内容治理需求文档.md。
"""

import re
import sys
import json
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "PRD" / "内容治理需求文档.md"
ART_PATH = ROOT / "research" / "governance" / "audit_rule_table.py"

# ── 正确做法：复用已经过验证的 split_md_row（它做还原） ────────────────
_spec = importlib.util.spec_from_file_location("art", ART_PATH)
art = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(art)
split_md_row = art.split_md_row

# ── 错误做法（用于对照）：未做还原的朴素切分 ───────────────────────────
def split_naive(line):
    """缺省的 `line.split('|')`：把每个 | 都当分隔符，包括 \\| 里的。"""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def split_regex_wrong(line):
    """一个看起来对、实际错的写法：Python raw string 里 \\\\ 是**两个**反斜杠，
    所以 (?<!\\\\) 检查的是「前面有两个反斜杠」，对单个 \\| 不生效。"""
    return [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]


def load_table(lines, header_pred):
    start = next(i for i, l in enumerate(lines) if header_pred(split_md_row(l)))
    hdr = split_md_row(lines[start])
    rows, j = [], start + 2
    while j < len(lines) and lines[j].startswith("|"):
        cells = split_md_row(lines[j])
        if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
            rows.append(cells)
        j += 1
    return hdr, rows


def main():
    lines = DOC.read_text(encoding="utf-8").split("\n")
    as_json = "--json" in sys.argv

    rhdr, rules = load_table(lines, lambda c: "规则编号" in c and "边界类型" in c)
    dhdr, ads = load_table(lines, lambda c: "广告名称" in c and "平台" in c)

    # ── 1. 两种切分下的字段完整性 ──────────────────────────────────
    def integrity(rows, ncol, fn):
        bad = [r for r in rows if len(fn(r)) != ncol]
        return len(bad)

    # 需要保留原始行文本来测试朴素切分
    def raw_rows(header_first_cell):
        out, j = [], None
        for i, l in enumerate(lines):
            if l.startswith("|") and split_md_row(l) and split_md_row(l)[0] == header_first_cell:
                j = i + 2
                break
        while j < len(lines) and lines[j].startswith("|"):
            out.append(lines[j])
            j += 1
        return out

    rule_raw = raw_rows("规则编号")
    ad_raw = raw_rows("广告名称")
    rule_raw = [l for l in rule_raw if not all(re.fullmatch(r":?-{2,}:?", c)
                                               for c in split_md_row(l))]

    report = {
        "rule_table": {"rows": len(rules), "cols": len(rhdr)},
        "ad_table": {"rows": len(ads), "cols": len(dhdr)},
        "splitting": {},
    }

    for name, raw, ncol in (("规则表(21行)", rule_raw, len(rhdr)),
                            ("记录表(291行)", ad_raw, len(dhdr))):
        d = {
            "correct_restore": sum(1 for l in raw if len(split_md_row(l)) == ncol),
            "naive_split": sum(1 for l in raw if len(split_naive(l)) == ncol),
            "regex_lookbehind_wrong": sum(1 for l in raw
                                          if len(split_regex_wrong(l)) == ncol),
            "rows": len(raw),
            "rows_containing_escape": sum(1 for l in raw if "\\|" in l),
        }
        report["splitting"][name] = d

    # ── 2. 还原后正则是否有效 ──────────────────────────────────────
    rx = {}
    for r in rules:
        d = dict(zip(rhdr, r))
        raw = d.get("正则表达式") or ""
        if not raw:
            continue
        pats, lit = [], 0
        for p in art.split_patterns(raw):
            try:
                c = re.compile(p, re.IGNORECASE)
                pats.append(p)
                if "\\|" in p:
                    lit += 1
            except re.error:
                pass
        rx[d["规则编号"]] = {"patterns": len(pats), "dead_literal_pipe": lit,
                             "restored_ok": lit == 0 and len(pats) > 0}

    report["regex_after_restore"] = rx
    report["regex_all_valid"] = all(v["restored_ok"] for v in rx.values())

    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    W = 88
    print("=" * W)
    print("转义层审计：Markdown 表格里的 `\\|` 是保护符，不是内容")
    print("=" * W)

    print("\n### 1. 三种切分方式下，字段数完整的行数\n")
    hdr_line = ("表" + " " * 16 + "总行" + " " * 2 + "正确还原" + " " * 6
                + "朴素 split" + " " * 4 + "正则误写" + " " * 4 + "含转义行")
    print(hdr_line)
    print("-" * W)
    for name, d in report["splitting"].items():
        print(f"{name:<18}{d['rows']:>6}{d['correct_restore']:>12}"
              f"{d['naive_split']:>14}{d['regex_lookbehind_wrong']:>12}"
              f"{d['rows_containing_escape']:>10}")

    print("\n### 2. 规则正则：还原后是否有效\n")
    print(f"{'规则':<8}{'pattern数':>10}{'含字面竖线':>12}  状态")
    print("-" * W)
    for k, v in rx.items():
        st = "✓ 有效" if v["restored_ok"] else f"✗ {v['dead_literal_pipe']} 条失效"
        print(f"{k:<8}{v['patterns']:>10}{v['dead_literal_pipe']:>12}  {st}")
    print("-" * W)
    print(f"结论：{len(rx)} 条有正则的规则，"
          f"{'全部有效' if report['regex_all_valid'] else '存在失效 pattern'}")

    print("\n### 3. 这个审计存在的理由\n")
    print("  本项目在诊断过程中曾两次因为「未做转义还原」得出错误结论：")
    print("    · 04 号：把 `欧洲DE` 与 `DE` 做字符串比较，判 4 个正确账号为不一致")
    print("    · 05 号：用 re.split(r'(?<!\\\\)\\|') 切分，误判 178 处正则为失效")
    print("  两次都是同一个错误：**没有把数据从它的存储表示中还原出来。**")
    print("  这与委托方 `投放地区` 字段的问题在结构上完全相同。")
    print("=" * W)
    return 0


if __name__ == "__main__":
    sys.exit(main())
