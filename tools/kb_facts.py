#!/usr/bin/env python3
"""
kb_facts.py —— 需求知识库的**事实数字单一来源**

## 为什么存在

`research/kb/README.md` §一「一页纸现状」是这套知识库的门面：10 个数字，一眼
看完。它同时也是最容易腐烂的东西 —— 数字由人抄，重算一次就发现对不上。

本轮（B3.0）实测到三处，都是同一个病的不同形态：

  ① **逾期数每天自动漂移。** `tools/kb_query.py 2` 用 `load.today()` 当基准日，
     于是 09-16 生成的手册写「逾期 30 条」，09-17 跑同一条命令得到 33 条。
     手册里那条「可复现命令」复现不出手册里的数 —— 而且**没有任何东西会发现**。
     逾期是**数据的属性**，不是提问时刻的属性：基准日必须是快照日。
  ② **同一个数在两处自相矛盾。** README §四.4 与 `tools/kb_materials_lark.py`
     的 docstring 都写「材料 15 条里可读 5 条」，而同一个文件里的实测列算出来是
     4 条 —— 代码打印 4，散文写 5，谁也没红。
  ③ **散文里的数字没有重算入口。** 想核对只能人肉数一遍。

## 本脚本的规矩

**一个数字只写一次，且由脚本算。** README 里那段现状表变成生成块
（`<!-- facts:begin -->` … `<!-- facts:end -->`），散文里不再复述数字，
只指向这里。数字变了而块没重生成 → `--check` 变红。

**基准日 = 快照日。** 见 `load.basis_date()`。这样同一份快照永远算出同一组数，
而「今天的逾期」要靠重新拉快照得到 —— 与 §三.5「v1 不做实时同步」一致。

用法：
  python3 tools/kb_facts.py            # 重算并写回 README 的生成块
  python3 tools/kb_facts.py --check     # 只比对不改盘（退出码非 0 = 块已过期）
"""

import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "research", "kb"))
import load  # noqa: E402

KB = load.KB
LEDGER = os.path.join(KB, "台账-v1.json")
COVERAGE = os.path.join(KB, "覆盖报告.json")
EVIDENCE = os.path.join(KB, "证据映射.json")
ANALYSIS = os.path.join(KB, "结构分析.json")
README = os.path.join(KB, "README.md")

BEGIN = "<!-- facts:begin -->"
END = "<!-- facts:end -->"

IN_FLIGHT = ("进行中", "未开始", "已停滞")


def _rows(snap):
    led = json.load(open(LEDGER, encoding="utf-8"))
    rs = [r for r in led["records"] if r["role"] != "excluded"]
    return led, rs, snap


def compute(snap=None):
    """算出全部对外引用的事实数字。**每一个都必须是快照的纯函数。**"""
    if snap is None:
        snap = load.snapshot()
    led, rs, snap = _rows(snap)
    cov = json.load(open(COVERAGE, encoding="utf-8"))
    ev = json.load(open(EVIDENCE, encoding="utf-8"))
    an = json.load(open(ANALYSIS, encoding="utf-8"))

    basis = load.basis_date(snap)

    done = [r for r in rs if r.get("status") == "已完成"]
    free = [r for r in rs if r.get("status") in IN_FLIGHT]
    due = [r for r in rs if r.get("date_due") and r.get("status") != "已完成"]
    over = [r for r in due if load.days_between(r["date_due"], basis) > 0]

    src_records = sum(x["source_records"] for x in cov["coverage"])
    no_ev = sum(r["需求条数"] for r in ev["rows"] if not r["已声明证据数"])
    with_ev = sum(r["需求条数"] for r in ev["rows"] if r["已声明证据数"])

    # 材料可读性：唯一来源是 kb_materials_lark 的实测列
    sys.path.insert(0, os.path.join(load.REPO, "tools"))
    import kb_materials_lark as mat                                   # noqa: PLC0415
    readable = sum(1 for m in mat.MATERIALS if m["可读性"] == "ok")

    start_like = [f"{t.system}/{t.name}:{f}"
                  for t in snap.ledger_tables() for f in (t.fields or [])
                  if any(k in str(f) for k in ("开始", "启动"))]

    # 正负样本的证据落盘件：★ 它自己和自己打架（抬头 returned=8，盘上 5 条）。
    #   这里**独立解析一遍**（不复用 kb_classes 的解析器）—— E2 要在「登记表里写的数」
    #   与「重算出来的数」之间比对，两者必须来自不同的实现，否则那条检查是恒真的。
    smp_p = os.path.join(KB, "_evidence", "正负样本.raw.txt")
    smp_txt = open(smp_p, encoding="utf-8").read() if os.path.exists(smp_p) else ""
    smp_head = re.search(r"returned=(\d+)", smp_txt)
    smp_blocks = [b for b in smp_txt.split("\n  ---") if "分类 =" in b]
    smp_marked = sum(1 for b in smp_blocks if '备注（如处理结果/建议） = "样例"' in b)
    ext_p = os.path.join(KB, "外部标准库-v1.json")
    ext_doc = json.load(open(ext_p, encoding="utf-8")) if os.path.exists(ext_p) else {"entries": []}

    # 4 类知识库「有没有货」：四类各自的判据都取自**不同的制品**，
    # 这样这个数就不是某一张表的自述，而是四条独立证据的合计。
    rules_p = os.path.join(load.REPO, "research", "governance", "skeleton", "rules-v1.json")
    n_rules = len(json.load(open(rules_p, encoding="utf-8"))["rules"]) \
        if os.path.exists(rules_p) else 0
    prod_readable = sum(1 for m in mat.MATERIALS
                        if m.get("归属知识库") == "产品描述库" and m["可读性"] == "ok")

    f = {
        "basis_date": basis,
        "snapshot_id": snap.snapshot_id,
        "source_systems": len({x["system"] for x in cov["coverage"]}),
        "source_tables": sum(1 for t in snap.all() if not t.excluded),
        "source_tables_excluded": sum(1 for t in snap.all() if t.excluded),
        "source_tables_in_ledger": sum(1 for x in cov["coverage"] if x["included"]),
        "source_records": src_records,
        "visibility_gaps": len(snap.visibility_gaps()),
        "ledger_total": len(rs),
        "ledger_top": sum(1 for r in rs if r["level"] == "top"),
        "ledger_child": sum(1 for r in rs if r["level"] == "child"),
        "in_flight": len(free),
        "due_dated": len(due),
        "overdue": len(over),
        "done": len(done),
        "done_no_deliverable": sum(1 for r in done if not r.get("deliverable")),
        "cross_table_dups": an["duplicate_summary"]["cross_table_keys"],
        "evidence_items": ev["totals"]["declared_evidence"],
        "lines_with_evidence": ev["totals"]["lines_with_evidence"],
        "lines_total": len(ev["rows"]),
        "demands_with_evidence": with_ev,
        "demands_without_evidence": no_ev,
        "demands_unmapped": ev["totals"]["demands_unmapped"],
        "empty_tables": sum(1 for t in snap.all() if t.kind == "empty"),
        "start_like_fields": len(start_like),
        "samples_on_disk": len(smp_blocks),
        "samples_marked_sample": smp_marked,
        "samples_real": len(smp_blocks) - smp_marked,
        "samples_header_returned": int(smp_head.group(1)) if smp_head else None,
        "ext_entries": len(ext_doc.get("entries", [])),
        "ext_ratified": sum(1 for e in ext_doc.get("entries", [])
                            if e.get("status") == "ratified"),
        "materials_total": len(mat.MATERIALS),
        "materials_readable": readable,
        "materials_unreadable": len(mat.MATERIALS) - readable,
        "kb_lex_rules": n_rules,
        "kb_prod_readable": prod_readable,
        "kb_classes_ready": sum([
            len(ext_doc.get("entries", [])) > 0,
            (len(smp_blocks) - smp_marked) > 0,
            n_rules > 0,
            prod_readable > 0,
        ]),
        "kb_classes_total": 4,
    }
    f["done_no_deliverable_pct"] = (f["done_no_deliverable"] / f["done"]) if f["done"] else 0.0
    f["no_evidence_pct"] = (f["demands_without_evidence"] /
                            (f["demands_with_evidence"] + f["demands_without_evidence"])
                            if (f["demands_with_evidence"] + f["demands_without_evidence"]) else 0.0)
    return f


def render(f):
    """把事实渲染成 README 的生成块。**散文里不再复述这些数字。**"""
    L = [
        BEGIN,
        "",
        f"> 下表由 `python3 tools/kb_facts.py` 生成，基准日 = 快照日 "
        f"`{f['basis_date']}`（**不是今天**）。"
        "改数字的唯一方式是改数据，然后重跑本脚本。",
        "",
        "| 项 | 读数 |",
        "|---|---|",
        f"| 源系统 | {f['source_systems']} 套（creative / seo），"
        f"{f['source_tables']} 张表（另 {f['source_tables_excluded']} 张含敏感字段整体排除）"
        f"，其中 **{f['source_tables_in_ledger']} 张**进台账 |",
        f"| 源记录 | **{f['source_records']} 条**，可见性缺口 **{f['visibility_gaps']}** |",
        f"| 台账 | **{f['ledger_total']} 条** = 顶层 **{f['ledger_top']}** + "
        f"WBS 子任务 **{f['ledger_child']}** |",
        f"| 在跑 | **{f['in_flight']} 条** |",
        f"| 疑似逾期 | **{f['overdue']} 条**（仅在有计划完成日期的 {f['due_dated']} 条上可算） |",
        f"| 已完成无产出物记录 | **{f['done_no_deliverable']} / {f['done']}**"
        f"（{f['done_no_deliverable_pct']:.0%}） |",
        f"| 跨系统重复 | **{f['cross_table_dups']} 条** |",
        f"| 本地证据覆盖品线 | **{f['lines_with_evidence']} / {f['lines_total']}**"
        f"（只有吸奶器） |",
        f"| 零证据品线需求 | **{f['demands_without_evidence']} 条**"
        f"（{f['no_evidence_pct']:.0%}） |",
        f"| 材料收集可程序读取 | **{f['materials_readable']} / {f['materials_total']}**"
        f"（不可读 {f['materials_unreadable']}） |",
        f"| 4 类知识库有货的 | **{f['kb_classes_ready']} / {f['kb_classes_total']}**"
        f"（外部标准库 {f['ext_entries']} 条 · 真实样本 {f['samples_real']} 条 · "
        f"规则 {f['kb_lex_rules']} 条 · 产品材料可读 {f['kb_prod_readable']} 条） |",
        "",
        END,
    ]
    return "\n".join(L)


def splice(text, block):
    """把生成块换进 README。块不存在时硬失败 —— 不猜该插在哪。"""
    if BEGIN not in text or END not in text:
        raise SystemExit(f"[kb_facts] 硬失败：{os.path.relpath(README, load.REPO)} "
                         f"里找不到生成块标记 {BEGIN} … {END}")
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    return head + block + tail


def current_block(text):
    m = re.search(re.escape(BEGIN) + r".*?" + re.escape(END), text, re.S)
    return m.group(0) if m else None


def main():
    check = "--check" in sys.argv
    f = compute()
    block = render(f)
    text = open(README, encoding="utf-8").read()
    on_disk = current_block(text)
    if on_disk == block:
        print(f"✅ README 事实块与重算一致（基准日 {f['basis_date']}）")
        return 0
    if check:
        print("❌ README 事实块与重算不一致 —— 文档里的数字已经和台账脱钩。")
        print("   修复：python3 tools/kb_facts.py")
        if on_disk is None:
            print("   盘上根本没有生成块标记。")
        else:
            import difflib
            for line in list(difflib.unified_diff(on_disk.splitlines(), block.splitlines(),
                                                  "盘上", "重算", lineterm=""))[:40]:
                print("   " + line)
        return 1
    # ★ 先把新全文算出来，再开文件写 —— 顺序反了会**先截断再报错**。
    #   本脚本第一版就是这样：`open(README,"w").write(splice(...))` 里
    #   `open(...,"w")` 先求值（文件当场被截成 0 字节），随后 `splice` 抛
    #   「找不到生成块」，于是 README 被清空且没人报错。见 B3.0 复盘。
    new_text = splice(text, block)
    open(README, "w", encoding="utf-8").write(new_text)
    print(f"✅ 已写回 {os.path.relpath(README, load.REPO)} 的事实块"
          f"（基准日 {f['basis_date']}）")
    for k in ("ledger_total", "in_flight", "overdue", "materials_readable"):
        print(f"   {k} = {f[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
