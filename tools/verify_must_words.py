#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_must_words.py —— 行 43（元判据）的**机器半边**

## 行 43 要什么，以及它为什么不是执行验收项

验收表第 43 行原文：

> **文档治理，不作为执行验收项；清单 owner=法务。** 人工通读全文，用脚本 grep
> 「必须/不许/一律/永不」生成清单，逐条写出「构造什么输入、跑什么、看到什么结果
> 算红」；写不出具体失败条件的登记为愿望并从验收依据中剔除。反向检查本验收表：
> 每行 how 都必须落到具体样本与读数，出现「按文档要求验证」这类空话的行退回重写。

**该行 `verifiability` 列 = `manual`**，且首句自己声明「不作为执行验收项」。
所以本脚本：

* **不进 `verifier_map.json`** —— 给 `#43` 挂执行点，等于用一个工具去推翻
  一条已经定稿的判据。那与「三重指纹漂移」是同一个病，漂的只是语义不是字节；
* `#43` 于是仍留 `untested`，**读数不变**。

## 它做什么（三段，全是读数，不判红）

1. **清单**：三类文档里每一条含「必须 / 不许 / 一律 / 永不」的行，
   连同所在段落的定位；
2. **失败条件句式统计**：该行/该段是否出现「构造 / 断言 / 即红 / 判红 / 退 N」
   这类**可执行失败条件**的句式。没有的标 `wish`（愿望）；
3. **验收表空话读数**：本表 `method` 列里出现「按文档要求验证」「见文档」
   「参照上文」「按要求验证」这类**空指针**的行，逐条列出。

## ★ 它刻意**不判红**，理由是硬的

第 3 段是元判据的一部分，而**「空话出现多少次算问题」判据原文没给阈值**。
自己定一个阈值再标红，等于替委托方定了一条判据。
本项目一贯的口径是：未测 ≠ 通过 ≠ 红；而**「有读数但没阈值」是第四种**。
所以本脚本的结论行只说读数，不说什么算过。

## 它不证明什么（写在结论行里，也写在这里）

**「写出来的失败条件是不是真条件」永远是人的活。**
本脚本只能证明「这一段里有没有出现失败条件的_句式_」——
一个写成「断言 X 即红」但实际验的是别的东西的段落，本脚本会算它「有条件」。
所以它产出的是**给人看的清单**，不是验收结论。

## 退出码

  0 读到了并出完三段读数（**不表示任何一条通过**）
  1 保留未用（本脚本没有红的判据）
  2 未测：三类目标文档一个都读不到

## 用法

    python3 tools/verify_must_words.py
    python3 tools/verify_must_words.py --controls    # 反向对照
    python3 tools/verify_must_words.py --json        # 机器读
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TARGETS = (
    ("验收表", ROOT / "PMO" / "audit" / "验收表-v3-覆盖全部判据-20261017.md"),
    ("Playbook", ROOT / "Playbook" / "内容审查Agent-产品Playbook-v1.1.md"),
    ("技术方案", ROOT / "Playbook" / "技术解决方案-v1.md"),
)

#: 判据原文逐字点名的四个强制词。
MUST_WORDS = ("必须", "不许", "一律", "永不")

#: 判定「这一段里有可执行的失败条件」的句式。
#: ★ 只认**可执行**的：要先有动作（构造/跑/注入），后有判据（断言/即红/判红/退 N）。
#: 单有「必须」不算 —— 那正是「愿望」与「条件」的分界。
CONDITION_PATTERNS = (
    re.compile(r"构造[^。；\n]{0,40}(样本|输入|夹具)"),
    re.compile(r"(断言|判定)[^。；\n]{0,30}(即红|判红|为红|失败)"),
    re.compile(r"(即红|判红|算红|必须红|不得绿)"),
    re.compile(r"退出码\s*[:：=]?\s*[012]|退\s*[012]\b"),
    re.compile(r"(喂|注入|植入)[^。；\n]{0,30}(坏样本|样本|变异)"),
    re.compile(r"反向对照"),
    re.compile(r"跑一趟|跑一次|运行[^。；\n]{0,20}断言"),
)

#: 验收表 method 列里的「空指针」：读者照着做不了任何事。
#: ★ 这些只是**读数**，不判红（判据原文没给阈值）。
EMPTY_POINTER_PATTERNS = (
    re.compile(r"按文档要求验证"),
    re.compile(r"见文档"),
    re.compile(r"参照上文"),
    re.compile(r"详见[^。；\n]{0,20}文档"),
    re.compile(r"按要求执行"),
    re.compile(r"按规范执行"),
)


class Untested(Exception):
    pass


def has_condition(text: str) -> bool:
    return any(p.search(text) for p in CONDITION_PATTERNS)


def find_empty_pointers(text: str) -> list[str]:
    hits = []
    for p in EMPTY_POINTER_PATTERNS:
        m = p.search(text)
        if m:
            hits.append(m.group(0))
    return hits


def scan_doc(path: Path) -> list[dict]:
    """返回含强制词的行：[{line, word, text, has_condition, kind}]。"""
    out = []
    text = path.read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        words = [w for w in MUST_WORDS if w in line]
        if not words:
            continue
        out.append({
            "line": i,
            "words": words,
            "text": line.strip()[:160],
            # 判定条件用**整行**：失败条件常常写在同一行的后半句。
            # 若将来发现「条件写在下一行」的情形很多，再扩到段落 ——
            # 但那时要同时把「扩到段落」写进注释，否则读数会悄悄变宽。
            "has_condition": has_condition(line),
        })
    return out


def scan_acceptance_table_methods() -> list[dict]:
    """验收表 method 列的空指针读数。"""
    sys.path.insert(0, str(ROOT / "tools"))
    import verify_acceptance_run as v  # noqa: PLC0415  —— 复用同一个解析器，不写第二份

    rows = v.parse_table(ROOT / "PMO" / "audit" / "验收表-v3-覆盖全部判据-20261017.md")
    out = []
    for r in rows:
        hits = find_empty_pointers(r["method"])
        if hits:
            out.append({"n": r["n"], "hits": hits,
                        "method": r["method"][:160]})
    return out


def build_report(root: Path = ROOT) -> dict:
    sections = {}
    missing = []
    for label, path in TARGETS:
        if not path.is_file():
            missing.append(f"{label}: {path.relative_to(root)}")
            continue
        sections[label] = scan_doc(path)
    if not sections:
        raise Untested("三类目标文档一个都读不到")

    total_lines = sum(len(v) for v in sections.values())
    total_wish = sum(1 for v in sections.values() for e in v if not e["has_condition"])
    return {
        "sections": sections,
        "missing": missing,
        "totals": {
            "must_word_lines": total_lines,
            "with_condition": total_lines - total_wish,
            "wish": total_wish,
        },
        "empty_pointers": scan_acceptance_table_methods(),
    }


def emit_text(rep: dict) -> None:
    print("=" * 78)
    print("行 43 · 强制词清单（机器半边）—— 只出读数，不判红")
    print("=" * 78)
    for label, entries in rep["sections"].items():
        wish = [e for e in entries if not e["has_condition"]]
        print(f"\n【{label}】含强制词 {len(entries)} 行 · "
              f"有失败条件句式 {len(entries) - len(wish)} · 愿望 {len(wish)}")
        for e in entries:
            mark = "  " if e["has_condition"] else "⚠ "
            print(f"  {mark}L{e['line']:<5} [{'/'.join(e['words'])}] {e['text'][:90]}")
    t = rep["totals"]
    print("\n" + "-" * 78)
    print(f"合计：{t['must_word_lines']} 行含强制词 · "
          f"{t['with_condition']} 行有失败条件句式 · {t['wish']} 行是愿望")
    ep = rep["empty_pointers"]
    print(f"验收表空指针读数：{len(ep)} 行 method 出现「按文档要求验证 / 见文档 / 参照上文」这类表述")
    for e in ep:
        print(f"  · #{e['n']} [{', '.join(e['hits'])}] {e['method'][:80]}")
    if rep["missing"]:
        print("\n⚠ 读不到的目标（这些没被扫）：")
        for m in rep["missing"]:
            print(f"  · {m}")
    print("-" * 78)
    print("★ 这份输出**不证明任何一条被验过**：")
    print("  · 「有失败条件句式」只说明那一段写了动作与判据，不说明验的是同一件事；")
    print("  · 「愿望 0 条」不表示强制词都可证伪，只表示句式都在；")
    print("  · 空指针只给读数 —— 判据原文没给阈值，本脚本不替你定「多少行算问题」。")
    print("  · 判断「写出来的失败条件是不是真条件」永远是人的活（owner=法务）。")
    print("\n★ 本脚本不进 verifier_map：#43 在表里是 manual，且首句写着")
    print("  「不作为执行验收项」。给它挂执行点等于用工具推翻一条已定稿的判据。")


def emit_json(rep: dict) -> None:
    print(json.dumps(rep, ensure_ascii=False, indent=2))


# ── 反向对照 ────────────────────────────────────────────────────────────────

def controls() -> int:
    """喂已知样本，证明分类器两个方向都对。

    ★ 缺任一条就有一个方向恒真：
      C1 有强制词 + 无失败条件 → 必须判 wish（否则「愿望」永远数不出来）
      C2 有强制词 + 有失败条件 → 必须判「有条件」（否则全是 wish，读数无意义）
      C3 空指针样本 → 必须被数出来
      C4 反向对照：正常句子不含空指针 → **不许**被误报
      C5 「单有『必须』但没有任何可执行动作」→ wish（这是本条的分界线）
      C6 「构造样本…即红」→ 有条件（正面样本，证明 C5 不是恒真）
    """
    results = []

    def ok(name, cond, detail=""):
        results.append((name, bool(cond), detail))

    c1 = has_condition("系统必须保证日志不丢失。")
    ok("C1 有强制词、无失败条件 → 判 wish", c1 is False, f"has_condition={c1}")

    c2 = has_condition("构造一条缺 authority_state 的样本，断言页面显示「未测」即红。")
    ok("C2 有强制词、有失败条件 → 判「有条件」", c2 is True, f"has_condition={c2}")

    c3 = find_empty_pointers("按文档要求验证即可。")
    ok("C3 空指针样本 → 必须被数出来", c3 == ["按文档要求验证"], str(c3))

    c4 = find_empty_pointers("构造一条空 quote 的样本，断言被拒即红。")
    ok("C4 ★ 反向对照：正常句子 → 不许被误报为空指针", c4 == [], str(c4))

    c5 = has_condition("必须一律永不删除。")
    ok("C5 只有强制词堆叠、无可执行动作 → wish", c5 is False, f"has_condition={c5}")

    c6 = has_condition("退出码 1 表示有红。")
    ok("C6 ★ 正面样本：写明了退出码也算可执行条件", c6 is True, f"has_condition={c6}")

    print("=" * 78)
    print("行 43 机器半边 · 反向对照")
    print("=" * 78)
    for name, good, detail in results:
        print(f"  {'✅' if good else '❌'} {name}" + (f"  ← {detail}" if not good else ""))
    print("-" * 78)
    bad = [n for n, g, _ in results if not g]
    if bad:
        print(f"❌ {len(bad)}/{len(results)} 项失败：{bad}")
        return 1
    print(f"✅ {len(results)}/{len(results)} 项全过（该红、该绿两侧都在）")
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if "--controls" in argv:
        return controls()
    try:
        rep = build_report()
    except Untested as exc:
        print(f"⚠ 未测：{exc}")
        return 2
    if "--json" in argv:
        emit_json(rep)
    else:
        emit_text(rep)
    # ★ 恒退 0（只要读得到）：本脚本没有红的判据。
    return 0


if __name__ == "__main__":
    sys.exit(main())
