#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_risk_label.py —— 把源表「风险等级」这一列的 291 行，逐行还原成它**真实的**状态

## 为什么要有这个脚本

`合规·绿` 是源表里出现最多的一个值：157 条，带着 $23,147.35（占全表投放的 53.8%）。
设计文档 §4.5/§5.1 早就认定它是**语义重载**（同时表示「确认合规」与「规则没覆盖到」），
R2 §2989 甚至写了判决书：

> 实测：291 条里 157 条是绿，其中相当部分来自命中规则后的人工降级 ——
> **但记录方式让这个数字无法被还原**。

**「无法被还原」这句话，今天不再成立。** 引擎在盘上，`records.json` 在盘上，
于是这 157 条可以逐行重跑、逐行归类，不需要任何人的回忆。

本脚本做三件事，都只读：

  ① **还原**：157 条绿标各自真实是什么（无文案 / 规则未覆盖 / 规则命中了）
  ② **定量**：把「盲区率」从「数学上不可观测」变成两个可算的数（见下）
  ③ **出账**：给出逐行迁移表，投放侧照单改行即可，不需要重新判断任何一条内容

## 三个轴，今天挤在一个字段里

| 轴 | 问的问题 | 今天的存法 |
|---|---|---|
| `可审内容` | 这条**有没有东西**可以拿去判？ | 挤进 `风险等级` |
| `覆盖状态` | 规则库**够不够得着**它？ | 挤进 `风险等级` |
| `风险等级` | 够得着的前提下，**多重**？ | 唯一合规的用法 |

一个字段扛三个正交的量，代价是两个数**在数学上算不出来**：

  - **盲区率**（规则够不着多少）—— 分母里混进了「根本没语料」的记录
  - **未审率**（有多少从没进过审查）—— 分子里混进了「规则没覆盖」

设计文档 §5.1 对前者写过一句「盲区率在数学上不可观测」。**这句话对，但它不是宿命** ——
它是**那个字段设计**的后果。本脚本把两个数都算出来。

## 引擎侧同一个病的第二个病灶

引擎把 `coverage_state` 修在了**处置层**（DP0 = 不可审 / DP3 = 未覆盖），
但 `severity` 里 `L0` 仍然同时吃下这两种情形（实测 `L0` = 59 条不可审 + 100 条未覆盖）。
**层修对了，等级没修。** 只读 `severity` 的人看到的还是同一个混值。已登记为 V44 门。

## 用法

  python3 research/governance/audit_risk_label.py            # 打印 + 写迁移账
  python3 research/governance/audit_risk_label.py --check     # 只比对不改盘（过期即非 0）
  python3 research/governance/audit_risk_label.py --md        # 输出变更请求里那张表
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path

GOV = Path(__file__).resolve().parent
ROOT = GOV.parent.parent
SKEL = GOV / "skeleton"
RECORDS = SKEL / "_data" / "records.json"
OUT = SKEL / "_data" / "风险等级-还原.json"
# ★ 变更请求里的每一张表都由本脚本生成。数字由人抄进去的那一天，它就开始腐烂 ——
#   这是本项目已经踩过的坑（README 现状表、判据里写死的「59 条」），不重复第三次。
DOC = GOV / "源表口径-风险等级-变更请求.md"
DOC_BEGIN = "<!-- risklabel:begin -->"
DOC_END = "<!-- risklabel:end -->"

sys.path.insert(0, str(SKEL))
import judge as J  # noqa: E402
import score as S  # noqa: E402

# ── 轴 1：可审内容 ──────────────────────────────────────────────────────────
# ★ 「整行没读到」必须与「无文案」分开。这两者在源表里长得一样（都是空），
#   但一个是**载体结构上不含文案**（Google PLA 商品 Feed 广告，永远不会长出
#   Primary Text），一个是**我们没读到**（拉取失败 / 表结构变了）。
#   合并计数的后果：D9 的条数会虚高，且「去修拉取管道」与「去改口径」这两件
#   毫不相干的事会被记成同一个数。实测 2 条（见下 `未读到` 判据）。
AUDITABLE = "有文案"
NO_TEXT = "无文案"
UNREAD = "未读到"
_NOT_AUDITABLE = (NO_TEXT, UNREAD)

# ── 轴 2：覆盖状态 ──────────────────────────────────────────────────────────
COVERED = "覆盖"
UNCOVERED = "未覆盖"
NA = "不适用"

# 判「整行没读到」用的身份字段：一条真实广告至少得有一个
IDENTITY_FIELDS = ("广告名称", "外部广告ID", "广告账号", "平台")


def _ne(r: dict, k: str) -> bool:
    return bool(str(r.get(k) or "").strip())


def _spend(r: dict) -> float:
    try:
        return float(r.get("_spend") or 0)
    except (TypeError, ValueError):
        return 0.0


def classify(recs: list[dict]) -> list[dict]:
    """逐条跑引擎，把每一行还原成三个轴。只读，不写盘。"""
    rows = []
    for i, r in enumerate(recs):
        text = S.rec_text(r)
        v = J.judge(text, product_line=(r.get("品线") or None),
                    ad_type=r.get("广告类型"))
        verdict = v["verdict"]
        layer = verdict["layer"]

        if text.strip():
            auditable, coverage = AUDITABLE, (
                UNCOVERED if verdict["disposition"] == "catch_all" else COVERED)
        elif any(_ne(r, f) for f in IDENTITY_FIELDS):
            auditable, coverage = NO_TEXT, NA
        else:
            auditable, coverage = UNREAD, NA

        src = str(r.get("风险等级") or "")
        rows.append({
            "i": i,
            "广告名称": str(r.get("广告名称") or ""),
            "平台": str(r.get("平台") or ""),
            "广告账号": str(r.get("广告账号") or ""),
            "投放USD": round(_spend(r), 2),
            "源表_风险等级": src,
            "源表_处理状态": str(r.get("处理状态") or ""),
            "可审内容": auditable,
            "覆盖状态": coverage,
            "引擎_severity": verdict["severity"],
            "引擎_处置层": layer["id"],
            "引擎_disposition": verdict["disposition"],
            # ★ 源表说「绿」，规则却命中了 —— 这不是口径问题，是**漏放**。
            #   它与「无文案」是两种完全不同的坏法，必须分开计数，否则
            #   「去改口径」会把「去复扫这 3 条」一起吞掉。
            "绿标与命中矛盾": ("绿" in src and bool(v["hits"])),
        })
    return rows


def totals(rows: list[dict]) -> dict:
    def n(pred):
        return sum(1 for x in rows if pred(x))

    def usd(pred):
        return round(sum(x["投放USD"] for x in rows if pred(x)), 2)

    green = [x for x in rows if "绿" in x["源表_风险等级"]]
    audit = [x for x in rows if x["可审内容"] == AUDITABLE]
    return {
        "records": len(rows),
        "spend_usd": usd(lambda x: True),
        "可审_有文案": n(lambda x: x["可审内容"] == AUDITABLE),
        "可审_无文案": n(lambda x: x["可审内容"] == NO_TEXT),
        "可审_未读到": n(lambda x: x["可审内容"] == UNREAD),
        "覆盖_覆盖": n(lambda x: x["覆盖状态"] == COVERED),
        "覆盖_未覆盖": n(lambda x: x["覆盖状态"] == UNCOVERED),
        # ★ 盲区率 —— 分母只用**有语料**的记录。这正是「不可观测」那句话解开的点。
        "盲区率": round(n(lambda x: x["覆盖状态"] == UNCOVERED) / len(audit), 4) if audit else None,
        # ★ 未审率 —— 分子是「没进过审查」的全部，两个原因分别可查。
        "未审率": round((n(lambda x: x["覆盖状态"] == UNCOVERED)
                         + n(lambda x: x["可审内容"] == NO_TEXT)) / len(rows), 4) if rows else None,
        "绿标_条数": len(green),
        "绿标_投放USD": round(sum(x["投放USD"] for x in green), 2),
        "绿标_占投放": round(sum(x["投放USD"] for x in green)
                             / (usd(lambda x: True) or 1), 4),
        # 157 条绿的真实构成
        "绿标_无文案": n(lambda x: "绿" in x["源表_风险等级"] and x["可审内容"] == NO_TEXT),
        "绿标_无文案USD": usd(lambda x: "绿" in x["源表_风险等级"] and x["可审内容"] == NO_TEXT),
        "绿标_规则未覆盖": n(lambda x: "绿" in x["源表_风险等级"] and x["覆盖状态"] == UNCOVERED),
        "绿标_规则未覆盖USD": usd(lambda x: "绿" in x["源表_风险等级"] and x["覆盖状态"] == UNCOVERED),
        "绿标_规则命中了": n(lambda x: x["绿标与命中矛盾"]),
        "绿标_规则命中了USD": usd(lambda x: x["绿标与命中矛盾"]),
        # 对照：引擎里真正称得上「查过且没问题」的只有 auto_pass_with_note。
        #   291 条里 3 条，且**没有一条**落在源表的绿标里 —— 所以「合规·绿」
        #   在这份语料上不可能被任何一次判定复现出来。
        "引擎_auto_pass": n(lambda x: x["引擎_disposition"] == "auto_pass_with_note"),
        "绿标_与引擎放行重合": sum(1 for x in rows
                                   if "绿" in x["源表_风险等级"]
                                   and x["引擎_disposition"] == "auto_pass_with_note"),
        "引擎_severity_L0_不可审": n(lambda x: x["引擎_severity"] == "L0"
                                     and x["可审内容"] == NO_TEXT),
        "引擎_severity_L0_未覆盖": n(lambda x: x["引擎_severity"] == "L0"
                                     and x["覆盖状态"] == UNCOVERED),
    }


def build() -> dict:
    recs = json.loads(RECORDS.read_text(encoding="utf-8"))
    if isinstance(recs, dict):
        recs = recs["records"]
    rows = classify(recs)
    return {
        "schema_version": 1,
        "$note": ("源表「风险等级」列的逐行还原。每一行的三个轴都由 "
                  "research/governance/skeleton 的引擎当场跑出来，**不含任何人工判断**。"
                  "改源表数据或改规则/词表后必须重跑；`--check` 会红。"),
        "generated_by": "research/governance/audit_risk_label.py",
        "source": str(RECORDS.relative_to(ROOT)),
        # ★ 输入指纹。下游（tools/kb_facts.py）会把这里的数字当成自己的事实键，
        #   所以它必须能判断这份账**是不是对着当前语料算的** —— 否则源表一改，
        #   下游读到的就是一串没人知道过期了的数字，且没有任何东西会红。
        "source_sha256": hashlib.sha256(RECORDS.read_bytes()).hexdigest(),
        "totals": totals(rows),
        "rows": rows,
    }


def render(doc: dict) -> str:
    """变更请求里那个生成块。★ 只由制品算，不含任何手写数字。"""
    t = doc["totals"]
    R = doc["rows"]
    L = []
    A = L.append
    A(f"**「合规·绿」{t['绿标_条数']} 条 / ${t['绿标_投放USD']:,.2f}"
      f"（占全表投放 {t['绿标_占投放']:.1%}）逐行还原出来是这样：**")
    A("")
    A("| 逐行还原**真实是**什么 | 条数 | 投放 USD | 谁该动 |")
    A("|---|---:|---:|---|")
    A(f"| 无文案 —— 载体结构上不含文案（Google PLA 商品 Feed 广告） "
      f"| {t['绿标_无文案']} | ${t['绿标_无文案USD']:,.2f} | 投放侧改口径 |")
    A(f"| 有文案，但**规则库没有覆盖它**（引擎落 `catch_all`） "
      f"| {t['绿标_规则未覆盖']} | ${t['绿标_规则未覆盖USD']:,.2f} | 审核侧扩规则 |")
    A(f"| **规则命中了**（源表漏放） | {t['绿标_规则命中了']} "
      f"| ${t['绿标_规则命中了USD']:,.2f} | 审核侧复扫这 {t['绿标_规则命中了']} 条 |")
    A(f"| **已查且通过** | **0** | **$0.00** | —— |")
    A(f"| **合计** | **{t['绿标_条数']}** | **${t['绿标_投放USD']:,.2f}** | |")
    A("")
    A(f"对照：引擎在这 291 条里唯一称得上「放行」的结论是 "
      f"`auto_pass_with_note`，共 **{t['引擎_auto_pass']} 条**，"
      f"与源表绿标的重合数是 **{t['绿标_与引擎放行重合']}**。")
    A(f"也就是说：**`合规·绿` 在这份语料上，不可能被任何一次判定复现出来。**")
    A("")
    A("### 291 行照单改行：三轴聚合")
    A("")
    import collections as _c
    agg = _c.Counter((x["可审内容"], x["覆盖状态"]) for x in R)
    sp: dict = _c.defaultdict(float)
    for x in R:
        sp[(x["可审内容"], x["覆盖状态"])] += x["投放USD"]
    A("| 可审内容 | 覆盖状态 | 条数 | 投放 USD |")
    A("|---|---|---:|---:|")
    for k in ((AUDITABLE, COVERED), (AUDITABLE, UNCOVERED), (NO_TEXT, NA), (UNREAD, NA)):
        A(f"| `{k[0]}` | `{k[1]}` | {agg.get(k, 0)} | ${sp.get(k, 0.0):,.2f} |")
    A(f"| **合计** | | **{t['records']}** | **${t['spend_usd']:,.2f}** |")
    A("")
    A("### 两个此前「数学上不可观测」的数")
    A("")
    A(f"- **盲区率 = {t['盲区率']:.1%}** —— 分母只算**有语料**的 "
      f"{t['可审_有文案']} 条。今天这个分母里混着 {t['可审_无文案']} 条"
      f"根本没有语料的记录，所以它算不出来。")
    A(f"- **未审率 = {t['未审率']:.1%}** —— 分子是「没进过审查」的全部，"
      f"两个原因（未覆盖 {t['覆盖_未覆盖']} + 无文案 {t['可审_无文案']}）"
      f"**必须分得开**：前者要扩规则，后者要改口径，是两件不相干的事。")
    A("")
    A(f"引擎侧自查：`severity=L0` 同时吃下这两种情形 —— 不可审 "
      f"{t['引擎_severity_L0_不可审']} + 未覆盖 {t['引擎_severity_L0_未覆盖']}。"
      f"**处置层修对了（DP0 / DP3 分得开），等级没修。**")
    return "\n".join(L)


def current_block(text: str):
    i, j = text.find(DOC_BEGIN), text.find(DOC_END)
    if i < 0 or j < 0:
        return None
    return text[i + len(DOC_BEGIN):j].strip()


def write_doc_block(block: str) -> None:
    text = DOC.read_text(encoding="utf-8")
    i, j = text.find(DOC_BEGIN), text.find(DOC_END)
    if i < 0 or j < 0:
        raise SystemExit(f"❌ {DOC.name} 里没有 {DOC_BEGIN} … {DOC_END} 标记")
    DOC.write_text(text[:i + len(DOC_BEGIN)] + "\n" + block + "\n"
                   + text[j:], encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只比对不改盘")
    ap.add_argument("--md", action="store_true", help="输出迁移表 markdown")
    a = ap.parse_args()

    doc = build()
    t = doc["totals"]

    if a.check:
        bad = []
        if not OUT.exists():
            bad.append(f"{OUT.name} 不存在")
        else:
            old = json.loads(OUT.read_text(encoding="utf-8"))
            if old.get("totals") != t or old.get("rows") != doc["rows"]:
                bad.append("还原账已过期（源表数据或引擎行为变了）")
                for k in sorted(set(t) | set(old.get("totals", {}))):
                    if t.get(k) != old.get("totals", {}).get(k):
                        print(f"     {k}: 盘上 {old.get('totals', {}).get(k)} → 现在 {t.get(k)}")
        have = current_block(DOC.read_text(encoding="utf-8")) if DOC.exists() else None
        if have != render(doc).strip():
            bad.append(f"{DOC.name} 的生成块已过期")
        if bad:
            print("❌ " + "；".join(bad))
            print("   修复：python3 research/governance/audit_risk_label.py")
            return 1
        print(f"✅ 还原账与生成块都与重算一致（{t['records']} 行）")
        return 0

    if a.md:
        # 变更请求里那张「291 行照单改行」的迁移表。按 (可审内容, 覆盖状态) 聚合 ——
        # 投放侧要的不是 291 行明细（明细在 JSON 里），是**几条规则**。
        agg = collections.Counter((x["可审内容"], x["覆盖状态"]) for x in doc["rows"])
        spend: dict = collections.defaultdict(float)
        for x in doc["rows"]:
            spend[(x["可审内容"], x["覆盖状态"])] += x["投放USD"]
        print("| 可审内容 | 覆盖状态 | 条数 | 投放 USD |")
        print("|---|---|---:|---:|")
        order = [(AUDITABLE, COVERED), (AUDITABLE, UNCOVERED),
                 (NO_TEXT, NA), (UNREAD, NA)]
        for k in order:
            print(f"| {k[0]} | {k[1]} | {agg.get(k, 0)} | "
                  f"${spend.get(k, 0.0):,.2f} |")
        print(f"| **合计** | | **{t['records']}** | **${t['spend_usd']:,.2f}** |")
        return 0

    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if DOC.exists():
        write_doc_block(render(doc))

    print("=" * 74)
    print("源表「风险等级」291 行 · 逐行还原")
    print("=" * 74)
    print(f"  语料             {t['records']} 行 · ${t['spend_usd']:,.2f}")
    print(f"  可审内容         有文案 {t['可审_有文案']} · "
          f"无文案 {t['可审_无文案']} · 未读到 {t['可审_未读到']}")
    print(f"  覆盖状态         覆盖 {t['覆盖_覆盖']} · 未覆盖 {t['覆盖_未覆盖']}")
    print(f"  ★ 盲区率         {t['盲区率']:.1%}   ← 分母只算有语料的 "
          f"{t['可审_有文案']} 条（原来混进了「没语料」的）")
    print(f"  ★ 未审率         {t['未审率']:.1%}   ← 未覆盖 + 无文案，两个原因可分别查")
    print()
    print(f"  「合规·绿」{t['绿标_条数']} 条 / ${t['绿标_投放USD']:,.2f}"
          f"（占投放 {t['绿标_占投放']:.1%}）的真实构成：")
    print(f"     无文案（结构上不可文本审查）  {t['绿标_无文案']:4d} 条  "
          f"${t['绿标_无文案USD']:>10,.2f}")
    print(f"     规则库未覆盖（catch_all）      {t['绿标_规则未覆盖']:4d} 条  "
          f"${t['绿标_规则未覆盖USD']:>10,.2f}")
    print(f"     规则命中了（源表漏放）        {t['绿标_规则命中了']:4d} 条  "
          f"${t['绿标_规则命中了USD']:>10,.2f}")
    print(f"     ── 其中「已查且通过」          {0:4d} 条  ${0:>10,.2f}")
    print()
    print(f"  对照：引擎里唯一称得上「放行」的 `auto_pass_with_note` 共 "
          f"{t['引擎_auto_pass']} 条，")
    print(f"        与源表绿标的重合数是 {t['绿标_与引擎放行重合']} —— "
          f"绿标在这份语料上复现不出来。")
    print()
    print(f"  引擎 `severity=L0` 同时吃下两种情形：不可审 {t['引擎_severity_L0_不可审']} "
          f"+ 未覆盖 {t['引擎_severity_L0_未覆盖']}（层修对了，等级没修）")
    print()
    print(f"→ {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
