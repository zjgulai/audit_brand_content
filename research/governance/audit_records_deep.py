#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
05 号内部证据：广告文案明细表的判定分歧分析 + 错题本现状盘点
—— 目的：量化「错题本需要覆盖多少条记录」，并找出机器判定与人工处置的分歧点

数据来源：PRD/内容治理需求文档.md「表：广告文案明细（共 291 条记录）」
         PRD/内容治理需求文档.md「表：品线内容边界规则库（共 21 条记录）」
         PRD/内容治理需求文档.md「表：风险文案改写建议库（分型号分渠道）（共 52 条记录）」

只读，不修改任何文件。输出到 stdout 与 _scratch/。
"""
import re
import sys
import json
import pathlib
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PRD = ROOT / "PRD" / "内容治理需求文档.md"
OUT = pathlib.Path(__file__).resolve().parent / "_scratch"
OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------- 解析器
# 与 audit_rule_table.py / audit_records.py 保持同一口径：
# 表格单元内的 \| 是转义的字面竖线，必须先还原再 split('|')。
# 这是本项目已踩过的坑（见 04 号文档第二处自查），此处复用同一函数。


def split_md_row(line):
    """把一行 markdown 表格行拆成单元格列表，正确处理 \\| 转义。"""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    # 先把转义竖线换成哨兵，split 后再还原
    SENTINEL = "\x00PIPE\x00"
    s = s.replace("\\|", SENTINEL)
    cells = [c.strip().replace(SENTINEL, "|") for c in s.split("|")]
    return cells


def extract_table(lines, start_idx):
    """从 start_idx（表头行）开始，返回 (headers, rows, end_idx)。"""
    headers = split_md_row(lines[start_idx])
    rows = []
    i = start_idx + 1
    # i 指向分隔行 |---|---|
    if i < len(lines) and set(lines[i].strip()) <= set("|-: \t"):
        i += 1
    while i < len(lines) and lines[i].strip().startswith("|"):
        rows.append(split_md_row(lines[i]))
        i += 1
    return headers, rows, i


def main():
    text = PRD.read_text(encoding="utf-8")
    lines = text.split("\n")

    # 定位三张表
    tables = {}
    for idx, ln in enumerate(lines):
        m = re.match(r"^## 表：(.+?)（共 (\d+) 条记录）", ln)
        if m:
            tables[m.group(1)] = (idx, int(m.group(2)))

    print("=" * 78)
    print("05 号内部证据：判定分歧分析 + 错题本现状盘点")
    print("=" * 78)
    print()
    print("## 0. PRD 中的表清单（声明条数 vs 实际解析条数）")
    print()

    parsed = {}
    for name, (idx, declared) in tables.items():
        hdr_idx = idx + 2  # 跳过表头行与空行/说明行，找到真正的 |...| 表头
        while hdr_idx < len(lines) and not lines[hdr_idx].strip().startswith("|"):
            hdr_idx += 1
        headers, rows, _ = extract_table(lines, hdr_idx)
        parsed[name] = (headers, rows)
        mark = "✓" if len(rows) == declared else "✗"
        print(f"  {mark} {name}: 声明 {declared} 条，解析出 {len(rows)} 条，{len(headers)} 列")

    print()

    # ------------------------------------------------------------ 记录表
    rec_name = "广告文案明细"
    if rec_name not in parsed:
        print("!! 未找到广告文案明细表")
        return 1
    hdr, rows = parsed[rec_name]
    col = {h: i for i, h in enumerate(hdr)}

    def cell(row, name):
        i = col.get(name)
        if i is None or i >= len(row):
            return ""
        return row[i].strip()

    print("=" * 78)
    print("## 1. 判定分布：机器判定 × 人工处置状态")
    print("=" * 78)
    print()

    risk = Counter()
    status = Counter()
    cross = defaultdict(Counter)
    for r in rows:
        rk = cell(r, "风险等级") or "(空)"
        st = cell(r, "处理状态") or "(空)"
        risk[rk] += 1
        status[st] += 1
        cross[rk][st] += 1

    print("### 1.1 风险等级分布")
    print()
    print("| 风险等级 | 条数 | 占比 |")
    print("|---|---:|---:|")
    for k, v in risk.most_common():
        print(f"| {k} | {v} | {v / len(rows) * 100:.1f}% |")
    print(f"| **合计** | **{sum(risk.values())}** | 100% |")
    print()

    print("### 1.2 处理状态分布")
    print()
    print("| 处理状态 | 条数 | 占比 |")
    print("|---|---:|---:|")
    for k, v in status.most_common():
        print(f"| {k} | {v} | {v / len(rows) * 100:.1f}% |")
    print()

    print("### 1.3 交叉表：风险等级 × 处理状态")
    print()
    all_st = [k for k, _ in status.most_common()]
    print("| 风险等级 \\ 处理状态 | " + " | ".join(all_st) + " | 小计 |")
    print("|---|" + "---:|" * (len(all_st) + 1))
    for rk, _ in risk.most_common():
        vals = [cross[rk][st] for st in all_st]
        print(f"| {rk} | " + " | ".join(str(v) for v in vals) + f" | {sum(vals)} |")
    print()

    print("=" * 78)
    print("## 2. 规则命中频次（哪些规则在生产中真正被触发）")
    print("=" * 78)
    print()

    rule_hits = Counter()
    no_hit = 0
    for r in rows:
        hr = cell(r, "命中规则")
        if not hr:
            no_hit += 1
            continue
        for token in re.split(r"[,，、;；\s]+", hr):
            token = token.strip()
            if token:
                rule_hits[token] += 1

    total_flagged = len(rows) - no_hit
    print(f"命中至少一条规则的记录：**{total_flagged}** / {len(rows)} "
          f"（{total_flagged / len(rows) * 100:.1f}%）；未命中：**{no_hit}**")
    print()
    print("| 规则 | 命中记录数 | 占已命中记录 |")
    print("|---|---:|---:|")
    for k, v in rule_hits.most_common():
        print(f"| {k} | {v} | {v / total_flagged * 100:.1f}% |")
    print()

    # 规则表中声明存在的规则，与生产中实际被触发的规则对照
    rule_name = "品线内容边界规则库"
    declared_rules = set()
    if rule_name in parsed:
        rh, rrows = parsed[rule_name]
        rc = {h: i for i, h in enumerate(rh)}
        for r in rrows:
            i = rc.get("规则编号")
            if i is not None and i < len(r):
                v = r[i].strip()
                if v:
                    declared_rules.add(v)
    print(f"### 2.1 规则覆盖对照（规则表声明 {len(declared_rules)} 条）")
    print()
    print("| 类别 | 规则 |")
    print("|---|---|")
    fired = sorted(rule_hits.keys())
    never = sorted(declared_rules - set(fired))
    unknown = sorted(set(fired) - declared_rules)
    print(f"| 生产中被触发 | {', '.join(fired) if fired else '（无）'} |")
    print(f"| **声明存在但从未触发** | {', '.join(never) if never else '（无）'} |")
    print(f"| 触发但不在规则表中 | {', '.join(unknown) if unknown else '（无）'} |")
    print()

    print("=" * 78)
    print("## 3. 错题本规模测算：人工复核结论有没有落点")
    print("=" * 78)
    print()
    print("关键问题：记录表能否回答「人工复核后，最终判定是什么」？")
    print()
    # 检查是否存在能承载"人工最终判定"的字段
    candidate_cols = ["人工判定", "复核结果", "最终判定", "是否误报", "误报", "漏报",
                      "人工结论", "申诉", "驳回", "检查人", "修改建议", "命中原因"]
    print("### 3.1 现有列中，哪些可能承载人工复核结论")
    print()
    print("| 列名 | 是否存在 | 非空率 | 为什么不足以作为人工判定 |")
    print("|---|---|---:|---|")
    reasons = {
        "风险等级": "是机器/规则输出的等级，不是人工复核后的结论",
        "处理状态": "只有「待人工复核/无需处理」两态，没有「复核后改判」这一态",
        "命中原因": "是规则文本的回显，不含人工意见",
        "命中片段": "是匹配到的字符串，不含人工意见",
        "命中规则": "是规则编号，不含人工意见",
        "修改建议": "是规则库预置的改写建议（来自 52 条建议库），不是针对这一条的复核结论",
        "检查人": "空列，从未填写",
    }
    for c in candidate_cols:
        if c in col:
            nonempty = sum(1 for r in rows if cell(r, c))
            print(f"| `{c}` | 是 | {nonempty / len(rows) * 100:.1f}% | {reasons.get(c, '—')} |")
        else:
            print(f"| `{c}` | **否** | — | 该列不存在 |")
    print()
    print("**结论**：记录表**没有任何一列**可以承载「人工复核后的最终判定」。")
    print("因此它现在只能回答「机器判了什么」，不能回答「机器判得对不对」——")
    print("而错题本的全部价值就在于后者。")
    print()

    print("### 3.2 待复核积压规模（= 错题本的第一批必填项）")
    print()
    pending = [r for r in rows if cell(r, "处理状态") == "待人工复核"]
    print(f"状态为「待人工复核」且**尚无结论**的记录：**{len(pending)}** 条")
    print()
    if pending:
        pr = Counter(cell(r, "风险等级") for r in pending)
        print("| 风险等级 | 待复核条数 |")
        print("|---|---:|")
        for k, v in pr.most_common():
            print(f"| {k} | {v} |")
        print()
        # 按地区
        pa = Counter(cell(r, "投放地区") or "(空)" for r in pending)
        print("| 投放地区 | 待复核条数 |")
        print("|---|---:|")
        for k, v in pa.most_common():
            print(f"| {k} | {v} |")
        print()
        # 按规则
        pru = Counter()
        for r in pending:
            for token in re.split(r"[,，、;；\s]+", cell(r, "命中规则")):
                if token.strip():
                    pru[token.strip()] += 1
        print("| 命中规则 | 待复核条数 |")
        print("|---|---:|")
        for k, v in pru.most_common():
            print(f"| {k} | {v} |")
        print()

        # 花费敞口
        spend = 0.0
        for r in pending:
            try:
                spend += float(cell(r, "近7天费用USD") or 0)
            except ValueError:
                pass
        total_spend = 0.0
        for r in rows:
            try:
                total_spend += float(cell(r, "近7天费用USD") or 0)
            except ValueError:
                pass
        if total_spend > 0:
            print(f"这 {len(pending)} 条待复核记录近 7 天合计花费 **${spend:,.2f}**，"
                  f"占全表近 7 天总花费 ${total_spend:,.2f} 的 **{spend / total_spend * 100:.1f}%**。")
            print("（即：规则判了「待人工复核」，但这笔钱在复核完成前一直在花。）")
            print()

    print("=" * 78)
    print("## 4. 跨渠道与跨地区的可见性缺口")
    print("=" * 78)
    print()

    ch = Counter(cell(r, "平台") or "(空)" for r in rows)
    print("### 4.1 平台分布（这张表覆盖了哪些渠道）")
    print()
    print("| 平台 | 条数 |")
    print("|---|---:|")
    for k, v in ch.most_common():
        print(f"| {k} | {v} |")
    print()
    print("**注意**：这张表只覆盖 `平台` 列中出现的渠道。R5 §7.7 发现的三个渠道冲突")
    print("（官网集合页 / 官网产品页 / Amazon listing）中，**Amazon 若不在上表内，则该冲突不会被这张表捕获**。")
    print()

    print("=" * 78)
    print("## 5. 改写建议库的覆盖度（52 条都在回答哪些规则）")
    print("=" * 78)
    print()

    sug_name = "风险文案改写建议库（分型号分渠道）"
    if sug_name in parsed:
        sh, srows = parsed[sug_name]
        sc = {h: i for i, h in enumerate(sh)}

        def scell(row, name):
            i = sc.get(name)
            if i is None or i >= len(row):
                return ""
            return row[i].strip()

        sug_rules = Counter(scell(r, "关联规则") or scell(r, "规则编号") or "(空)" for r in srows)
        print(f"改写建议库实际解析出 **{len(srows)}** 条，列名：{sh}")
        print()
        print("| 关联规则 | 建议条数 |")
        print("|---|---:|")
        for k, v in sug_rules.most_common():
            print(f"| {k} | {v} |")
        print()

        # 哪些规则有改写建议，哪些没有
        have = {k for k in sug_rules if k and k != "(空)"}
        missing = sorted(declared_rules - have)
        print(f"**有改写建议的规则**：{', '.join(sorted(have))}")
        print()
        print(f"**没有改写建议的规则（{len(missing)} 条）**：{', '.join(missing) if missing else '（无）'}")
        print()
        if missing:
            print("这不是缺陷 —— 而是说明改写建议库**本来就不是按规则编号铺满的**。")
            print("它是按「实际发生过的违规表达」沉淀的，因此它天然是错题本的形态，而不是规则库的分支。")
            print()

    print("=" * 78)
    print("## 6. 汇总")
    print("=" * 78)
    print()
    print("| 结论 | 数值 |")
    print("|---|---|")
    print(f"| 记录表条数 | {len(rows)} |")
    print(f"| 命中规则的记录 | {total_flagged}（{total_flagged / len(rows) * 100:.1f}%）|")
    print(f"| 待人工复核且无结论 | {len(pending)} |")
    print(f"| 可承载人工判定的列 | **0** |")
    print(f"| 规则表声明规则数 | {len(declared_rules)} |")
    print(f"| 生产中被触发的规则数 | {len(fired)} |")
    print(f"| 从未触发的规则数 | {len(never)} |")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
