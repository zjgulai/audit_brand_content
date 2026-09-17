#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
291 条在跑记录的第二轮审计：判定层的一致性、可解析性、以及「错题本」缺什么字段。

要回答的问题：
  6. 「命中规则」字段的书写格式有几种？能不能被机器解析？
  7. 风险等级与命中规则是否自洽？（命中 M 类却标红 / 命中 H 类却标绿）
  8. 有命中片段却没命中规则的记录有多少？反向呢？
  9. 规则共现：哪些规则总是一起出现？（边界重叠的量化证据）
 10. 「检查人」字段的填写率 —— 没有检查人 = 没人复核，问责链断裂
 11. 错题本三要素（false positive / false negative / 规则出处）在现有字段里有没有位置

用法：python3 research/governance/audit_records.py
"""
import re
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRD = ROOT / "PRD" / "内容治理需求文档.md"


def split_md_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    cells, buf, i = [], [], 0
    while i < len(line):
        c = line[i]
        if c == "\\" and i + 1 < len(line) and line[i + 1] == "|":
            buf.append("|")
            i += 2
            continue
        if c == "|":
            cells.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    cells.append("".join(buf))
    return [c.strip() for c in cells]


def load_table(name_prefix):
    lines = PRD.read_text(encoding="utf-8").splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith("## 表：" + name_prefix)), None)
    if start is None:
        # 前缀匹配
        start = next((i for i, l in enumerate(lines)
                      if l.startswith("## 表：") and l[len("## 表："):].startswith(name_prefix)), None)
    hdr, rows = None, []
    for ln in lines[start + 1:]:
        if ln.startswith("#"):
            break
        if ln.startswith("|"):
            cells = split_md_row(ln)
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c != ""):
                continue
            if hdr is None:
                hdr = cells
            else:
                rows.append(dict(zip(hdr, cells)))
    return hdr, rows


def norm_level(s):
    s = (s or "").strip()
    if "红" in s:
        return "红"
    if "黄" in s:
        return "黄"
    if "绿" in s:
        return "绿"
    if "灰" in s:
        return "灰"
    return "(空)"


def main():
    hdr, ads = load_table("广告文案明细")
    print("=" * 78)
    print(f"广告明细：{len(ads)} 条 / {len(hdr)} 列")
    print("=" * 78)

    # ---------- 6. 命中规则字段的书写格式 ----------
    print()
    print("[6] 「命中规则」字段的可解析性")
    print("=" * 78)
    fmt = Counter()
    samples = defaultdict(list)
    for a in ads:
        raw = (a.get("命中规则") or "").strip()
        if not raw:
            fmt["(空)"] += 1
            continue
        ids = re.findall(r"\b[HMU]\d{2}\b|安全词", raw)
        # 去掉编号与常见分隔符后还剩什么
        rest = re.sub(r"\b[HMU]\d{2}\b|安全词", "", raw)
        rest = re.sub(r"[\s,，、;；/|+\-—:：()（）\[\]【】]+", "", rest)
        key = f"{'多个' if len(ids) > 1 else '单个'}编号 + {'有附加文本' if rest else '纯编号'}"
        fmt[key] += 1
        if len(samples[key]) < 3:
            samples[key].append(raw[:150])
    for k, v in fmt.most_common():
        print(f"  {k:<26}{v:>5}")
        for s in samples[k]:
            print(f"      例：{s}")

    # ---------- 7. 风险等级 vs 命中规则 自洽性 ----------
    print()
    print("[7] 风险等级 与 命中规则族 是否自洽")
    print("=" * 78)
    cross = defaultdict(Counter)
    inconsistent = []
    for a in ads:
        lvl = norm_level(a.get("风险等级"))
        ids = re.findall(r"\b[HMU]\d{2}\b|安全词", a.get("命中规则") or "")
        fams = {"H" if i.startswith("H") else "M" if i.startswith("M") else "U" if i.startswith("U") else "W" for i in ids}
        fam = "+".join(sorted(fams)) if fams else "(无)"
        cross[lvl][fam] += 1
        # 自洽规则：H→红, M→黄, U→灰, 安全词→绿, 无→绿
        expect = None
        if fams == {"H"}:
            expect = "红"
        elif fams == {"M"}:
            expect = "黄"
        elif fams == {"U"}:
            expect = "灰"
        elif not fams:
            expect = "绿"
        if expect and lvl != expect:
            inconsistent.append((a.get("广告名称", "")[:44], lvl, fam, a.get("命中规则", "")[:40]))
    fams_all = sorted({f for c in cross.values() for f in c})
    print(f"  {'风险等级':<10}" + "".join(f"{f:>10}" for f in fams_all))
    for lvl in ["红", "黄", "灰", "绿", "(空)"]:
        if lvl not in cross:
            continue
        print(f"  {lvl:<10}" + "".join(f"{cross[lvl].get(f, 0):>10}" for f in fams_all))
    print()
    print(f"  单一族 → 等级 不自洽的记录：{len(inconsistent)} 条")
    for s in inconsistent[:12]:
        print(f"    {s[0]:<46} 标{s[1]} / 命中{s[2]} / {s[3]}")

    # ---------- 8. 字段填写完整性 ----------
    print()
    print("[8] 关键字段填写率（问责链是否闭合）")
    print("=" * 78)
    for col in ["命中规则", "命中片段", "命中原因", "修改建议", "检查人", "风险等级", "处理状态"]:
        filled = sum(1 for a in ads if (a.get(col) or "").strip())
        print(f"  {col:<10}{filled:>5}/{len(ads)}  {filled/len(ads):>6.1%}")
    risky = [a for a in ads if norm_level(a.get("风险等级")) in ("红", "黄", "灰")]
    print()
    print(f"  非绿记录 {len(risky)} 条，其中：")
    for col in ["命中规则", "命中片段", "修改建议", "检查人"]:
        filled = sum(1 for a in risky if (a.get(col) or "").strip())
        print(f"    {col:<10}{filled:>5}/{len(risky)}  {filled/len(risky):>6.1%}")

    # ---------- 9. 规则共现 ----------
    print()
    print("[9] 规则共现（边界重叠的量化证据）")
    print("=" * 78)
    co = Counter()
    multi = 0
    for a in ads:
        ids = sorted(set(re.findall(r"\b[HMU]\d{2}\b|安全词", a.get("命中规则") or "")))
        if len(ids) > 1:
            multi += 1
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                co[(ids[i], ids[j])] += 1
    print(f"  命中 ≥2 条规则的记录：{multi} 条 / {len(ads)}")
    print(f"  共现次数最高的组合：")
    for (x, y), n in co.most_common(12):
        print(f"    {x} + {y:<8}{n:>5}")

    # ---------- 10. 平台 × 地区 × 规则 ----------
    print()
    print("[10] 命中规则 按平台 / 地区 / 语种分布（规则是否分维度）")
    print("=" * 78)
    for dim in ["平台", "投放地区", "文案语种", "品线"]:
        m = defaultdict(Counter)
        for a in ads:
            for rid in set(re.findall(r"\b[HMU]\d{2}\b", a.get("命中规则") or "")):
                m[a.get(dim, "(空)")][rid] += 1
        print(f"\n  按{dim}：")
        for k in sorted(m, key=lambda x: -sum(m[x].values()))[:8]:
            tot = sum(m[k].values())
            top = ", ".join(f"{r}×{n}" for r, n in m[k].most_common(5))
            print(f"    {k:<10}{tot:>5}  {top}")

    # ---------- 11. 错题本三要素 ----------
    print()
    print("[11] 「错题本」三要素在现有字段里有没有位置")
    print("=" * 78)
    need = {
        "false positive（Agent 判违规、人工判定合规）": ["误报", "误判", "false", "驳回", "推翻", "不成立", "已豁免"],
        "false negative（Agent 未判、人工补判违规）": ["漏判", "补充", "新增命中", "人工加", "漏检"],
        "规则出处（这条判定依据哪条规则、哪条规则从哪个案例来）": ["来源案例", "案例ID", "出处", "溯源"],
        "豁免依据（为什么这次不算违规）": ["豁免理由", "不判理由", "例外"],
        "证据（支撑素材的截图/链接/快照）": ["证据", "截图", "快照", "link", "url"],
    }
    allcols = " ".join(hdr)
    for label, keys in need.items():
        found = [k for k in keys if k.lower() in allcols.lower()]
        print(f"  {label}")
        print(f"      → 现有 27 列里{'找到：' + str(found) if found else '✗ 没有对应列'}")

    # 处理状态的取值
    print()
    st = Counter(a.get("处理状态", "") for a in ads)
    print("  「处理状态」实际取值：")
    for k, v in st.most_common():
        print(f"    {k or '(空)':<14}{v:>5}")

    out = ROOT / "research" / "governance" / "_evidence" / "record_audit.json"
    out.write_text(json.dumps({
        "total": len(ads),
        "format": dict(fmt),
        "level_x_family": {k: dict(v) for k, v in cross.items()},
        "inconsistent": len(inconsistent),
        "cooccurrence": [{"a": x, "b": y, "n": n} for (x, y), n in co.most_common(20)],
        "treatment_status": dict(st),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"机器可读结果已写入 {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
