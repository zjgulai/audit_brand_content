#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
规则库体检（lint）：把前面几轮的审计固化成一次可复跑的体检，输出记分卡。

设计意图：这份脚本就是 SOP 里「每月规则体检」那一步的可执行形态。
它不修改任何输入，只读 PRD 与记录表，输出 12 项检查的通过/告警/失败。

用法：
    python3 research/governance/lint_rules.py
    python3 research/governance/lint_rules.py --json     # 只输出 JSON
"""
import re
import sys
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_records as arc
import audit_rule_table as art

ROOT = Path(__file__).resolve().parents[2]

# ── 受控词表（体检时用于判定字段取值是否合法） ──────────────────────────
VALID_SEVERITY = {"高危", "审慎", "待复核", "合规"}
VALID_BOUNDARY = {"严格限制红线", "审慎关注", "人工复核", "安全词白名单"}
LANG_MARKERS = {
    "德语": re.compile(r"[äöüßÄÖÜ]"),
    "法语": re.compile(r"[àâçéèêëîïôûùœ]"),
    "西语": re.compile(r"[ñáíóú¿¡]"),
    "波兰语": re.compile(r"[ąćęłńóśźż]"),
    "意语": re.compile(r"[àèéìòù]"),
}
# 「口径放开」类措辞：出现即表示该词已被声明为不判险
RELEASED_PAT = re.compile(r"(放开|不再判险|允许|不判险|停用|已豁免)")
QUOTED = re.compile(r"[A-Za-z#][A-Za-z0-9#./'\- ]{1,40}")


def lang_of(term):
    for name, rx in LANG_MARKERS.items():
        if rx.search(term):
            return name
    if re.search(r"[\u4e00-\u9fff]", term):
        return "中文"
    if re.fullmatch(r"[A-Za-z0-9#./'\- ]+", term):
        return "英文"
    return "其他"


def main():
    emit_json = "--json" in sys.argv
    _, rules = art.load_rules()
    _, ads = arc.load_table("广告文案明细")

    R = {r["规则编号"]: r for r in rules}
    checks = []

    def add(cid, name, status, detail):
        checks.append({"id": cid, "name": name, "status": status, "detail": detail})

    # 去重素材
    seen = {}
    for a in ads:
        k = ((a.get("Primary Text") or "") + "||" + (a.get("Headline") or ""))
        if k.strip("|") and k not in seen:
            seen[k] = a
    creatives = list(seen.values())

    # ── C1 规则编号唯一且稳定 ─────────────────────────────────────────
    ids = [r["规则编号"] for r in rules]
    dup = [k for k, v in Counter(ids).items() if v > 1]
    add("C1", "规则编号唯一", "FAIL" if dup else "PASS",
        f"{len(ids)} 条规则，重复编号：{dup or '无'}")

    # ── C2 每条规则必须有出处（法源或案例），不能为空 ──────────────────
    no_src = [r["规则编号"] for r in rules if not (r.get("依据来源") or "").strip()]
    weak = [r["规则编号"] for r in rules
            if (r.get("依据来源") or "").strip() and
            not re.search(r"(xlsx|反馈|T\d|法|§|CFR|条例|第.{1,3}条)", r.get("依据来源") or "")]
    add("C2", "每条规则可溯源（法源／案例）",
        "FAIL" if no_src else ("WARN" if weak else "PASS"),
        f"无出处：{no_src or '无'}；出处过泛（未指向具体法条或案例）：{weak or '无'}")

    # ── C3 正则覆盖率：正则必须覆盖本规则词表 ────────────────────────
    low = []
    for r in rules:
        kws = [k.strip() for k in (r.get("检测关键词") or "").split(",") if k.strip()]
        pats = [p for p in (art.compile_rule_regex(r.get("正则表达式") or "") or [])
                if not isinstance(p, tuple)]
        if not kws or not pats:
            continue
        cov = sum(1 for k in kws if any(p.search(k) for p in pats)) / len(kws)
        if cov < 0.5:
            low.append(f"{r['规则编号']}={cov:.0%}")
    add("C3", "正则覆盖本规则词表 ≥50%", "WARN" if low else "PASS",
        f"覆盖率不足的规则：{low or '无'}")

    # ── C4 豁免词不得被本规则触发条件命中 ────────────────────────────
    selfcatch = []
    for r in rules:
        pats = [p for p in (art.compile_rule_regex(r.get("正则表达式") or "") or [])
                if not isinstance(p, tuple)]
        ex = [w.strip() for w in (r.get("豁免词") or "").split(",") if w.strip()]
        if not pats or not ex:
            continue
        hit = [w for w in ex if any(p.search(w) for p in pats)]
        if hit:
            selfcatch.append(f"{r['规则编号']}:{hit}")
    add("C4", "豁免词不被本规则自身命中", "FAIL" if selfcatch else "PASS",
        f"{selfcatch or '无'}")

    # ── C5 停用规则必须从生效集中移除 ────────────────────────────────
    disabled = [r["规则编号"] for r in rules
                if (r.get("启用状态") or "").strip() not in ("启用", "")]
    ghost = []
    for rid in disabled:
        kws = [k.strip().lower() for k in (R[rid].get("检测关键词") or "").split(",") if k.strip()]
        n = sum(1 for a in creatives
                if any(k in ((a.get("Primary Text") or "") + " " + (a.get("Headline") or "")).lower()
                       for k in kws))
        ghost.append(f"{rid}(匹配{n}条素材)")
    add("C5", "停用规则的词表已失效", "WARN" if disabled else "PASS",
        f"停用：{ghost or '无'}")

    # ── C6 编号族 ↔ (边界类型, 严重度) 一一对应 ──────────────────────
    cross = defaultdict(Counter)
    for r in rules:
        rid = r["规则编号"]
        pre = "安全词" if rid.startswith("安全词") else rid[:1]
        cross[pre][(r.get("边界类型", ""), r.get("风险等级", ""))] += 1
    multi = {k: dict(v) for k, v in cross.items() if len(v) > 1}
    add("C6", "编号族与(边界类型,严重度)一一对应", "WARN" if multi else "PASS",
        f"多义族：{multi or '无'}")

    # ── C7 严重度与边界类型取值合法 ─────────────────────────────────
    badsv = sorted({r.get("风险等级", "") for r in rules} - VALID_SEVERITY)
    badbd = sorted({r.get("边界类型", "") for r in rules} - VALID_BOUNDARY)
    add("C7", "严重度／边界类型取自受控词表",
        "FAIL" if (badsv or badbd) else "PASS",
        f"越界严重度：{badsv or '无'}；越界边界类型：{badbd or '无'}")

    # ── C8 词表的语种覆盖 vs 实际在跑的语种 ──────────────────────────
    table_langs = Counter()
    for r in rules:
        for k in (r.get("检测关键词") or "").split(","):
            k = k.strip()
            if k:
                table_langs[lang_of(k)] += 1
    for r in rules:
        for w in (r.get("豁免词") or "").split(","):
            w = w.strip()
            if w:
                table_langs[lang_of(w)] += 1
    running = Counter()
    for a in ads:
        lg = (a.get("文案语种") or "").strip()
        if lg and lg != "其他":
            running[lg] += 1
    missing = []
    for lg in ["德语", "法语", "西语", "意语", "波兰语"]:
        if table_langs.get(lg, 0) == 0:
            missing.append(lg)
    add("C8", "词表覆盖所有在跑语种", "FAIL" if missing else "PASS",
        f"词表语种分布={dict(table_langs)}；实际投放语种={dict(running)}；"
        f"零覆盖语种：{missing or '无'}")

    # ── C9 「口径放开」的词不得仍留在其他规则的词表里 ────────────────
    # 「best/#1/No.1/最佳/最好」这类用 / 或 、 并列书写，必须先拆开再比对，
    # 否则整串会被当成一个词，永远匹配不上。
    SPLITTER = re.compile(r"[/、,，]|等|以及|及")
    released = {}          # term -> 声明放开的规则
    for r in rules:
        for field in ("边界内容", "触发原因"):
            txt = r.get(field) or ""
            for seg in re.split(r"[；;。\n]", txt):
                if not RELEASED_PAT.search(seg):
                    continue
                for chunk in QUOTED.findall(seg):
                    for w in SPLITTER.split(chunk):
                        w = w.strip().strip("。，,;；:：").lower()
                        if 2 <= len(w) <= 30:
                            released.setdefault(w, r["规则编号"])
    conflicts = []
    for term, owner in released.items():
        for r in rules:
            if r["规则编号"] == owner:
                continue
            kws = [k.strip().lower() for k in (r.get("检测关键词") or "").split(",") if k.strip()]
            # 只有「规则词表里的完整词条以该放开词开头/结尾」才算候选冲突；
            # 子串包含（如 let-down 出现在 faster let-down 里）不算——那是限定形式的差别。
            for k in kws:
                if len(k) < 2:
                    continue
                if k == term or k.startswith(term + " ") or k.endswith(" " + term) \
                   or k in (term + "s", term + "seller", term + "-selling"):
                    conflicts.append(f"{owner} 声明放开 {term!r}，但 {r['规则编号']} 词表仍含 {k!r}")
                    break
    add("C9", "口径放开的词已从其他规则词表移除（候选，需人工确认）",
        "WARN" if conflicts else "PASS",
        f"{conflicts or '无候选冲突'}")

    # ── C10 触发条件完全重合的规则对（冗余） ────────────────────────
    kw = {r["规则编号"]: {k.strip().lower() for k in (r.get("检测关键词") or "").split(",") if k.strip()}
          for r in rules}
    pair_hits = Counter()
    for a in creatives:
        t = ((a.get("Primary Text") or "") + " " + (a.get("Headline") or "")).lower()
        fired = {rid for rid, ks in kw.items() if any(k in t for k in ks)}
        for x in sorted(fired):
            for y in sorted(fired):
                if x < y:
                    pair_hits[(x, y)] += 1
    redundant = [f"{x}+{y}(同现{n}次)" for (x, y), n in pair_hits.most_common(6) if n >= 8]
    add("C10", "无触发条件完全重合的规则对", "WARN" if redundant else "PASS",
        f"高同现规则对：{redundant or '无'}（同现≠冗余，需人工确认）")

    # ── C11 零命中规则 ──────────────────────────────────────────────
    fired = Counter()
    for a in ads:
        for rid in set(re.findall(r"\b[HMU]\d{2}\b", a.get("命中规则") or "")):
            fired[rid] += 1
    active = [r["规则编号"] for r in rules
              if (r.get("启用状态") or "").strip() == "启用" and not r["规则编号"].startswith("安全词")]
    never = [rid for rid in active if fired.get(rid, 0) == 0]
    add("C11", "无长期零命中的生效规则", "WARN" if never else "PASS",
        f"零命中：{never or '无'}（需区分「风险未发生」与「规则失效」，见 C12）")

    # ── C12 覆盖缺口必须是显式状态，不能默认合规 ────────────────────
    invisible = [a for a in ads
                 if not (a.get("Primary Text") or "").strip()
                 and not (a.get("Headline") or "").strip()]
    green_invisible = [a for a in invisible
                       if "绿" in (a.get("风险等级") or "")]
    add("C12", "不可判定的素材不落「合规」",
        "FAIL" if green_invisible else "PASS",
        f"无文案记录 {len(invisible)}/{len(ads)}，其中落绿 {len(green_invisible)} 条")

    # ── C13 判定可复现：规则表能否复现历史判定 ──────────────────────
    recorded = [(a, sorted(set(re.findall(r"\b[HMU]\d{2}\b", a.get("命中规则") or ""))))
                for a in ads
                if (a.get("命中规则") or "").strip() and a["命中规则"] != "EMPTY"]
    full = 0
    for a, ids_ in recorded:
        t = (a.get("Primary Text") or "") + " " + (a.get("Headline") or "")
        got = set()
        for r in rules:
            pats = [p for p in (art.compile_rule_regex(r.get("正则表达式") or "") or [])
                    if not isinstance(p, tuple)]
            if not pats:
                continue
            ex = [w.strip() for w in (r.get("豁免词") or "").split(",") if w.strip()]
            if any(re.search(re.escape(w), t, re.I) for w in ex):
                continue
            if any(p.search(t) for p in pats):
                got.add(r["规则编号"])
        if set(ids_) <= got:
            full += 1
    rate = full / max(1, len(recorded))
    add("C13", "规则表可复现历史判定 ≥80%",
        "PASS" if rate >= 0.8 else ("WARN" if rate >= 0.5 else "FAIL"),
        f"复现率 {full}/{len(recorded)} = {rate:.1%}")

    # ── C14 词表里的字面量数字（应改写为模式） ──────────────────────
    literal_num = []
    for r in rules:
        for k in (r.get("检测关键词") or "").split(","):
            k = k.strip()
            if re.search(r"\d", k) and not re.search(r"[\[\]()|\\*+?]", k):
                literal_num.append(f"{r['规则编号']}:{k}")
    add("C14", "含数字的声称写成模式而非字面量",
        "WARN" if literal_num else "PASS",
        f"{len(literal_num)} 条字面量含数字：{literal_num[:8]}{' …' if len(literal_num) > 8 else ''}")

    # ── 输出 ────────────────────────────────────────────────────────
    if emit_json:
        print(json.dumps({"checks": checks}, ensure_ascii=False, indent=2))
        return

    icon = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌"}
    n_pass = sum(1 for c in checks if c["status"] == "PASS")
    n_warn = sum(1 for c in checks if c["status"] == "WARN")
    n_fail = sum(1 for c in checks if c["status"] == "FAIL")

    print("=" * 100)
    print("规则库体检记分卡")
    print("=" * 100)
    for c in checks:
        print(f"\n{icon[c['status']]} {c['id']:<4}{c['name']}")
        print(f"      {c['detail']}")
    print()
    print("=" * 100)
    print(f"  通过 {n_pass} / 告警 {n_warn} / 失败 {n_fail}   共 {len(checks)} 项")
    print(f"  健康度：{n_pass/len(checks):.0%}")
    print("=" * 100)

    out = ROOT / "research" / "governance" / "_evidence" / "lint_scorecard.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(
        {"summary": {"pass": n_pass, "warn": n_warn, "fail": n_fail}, "checks": checks},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  机器可读结果：{out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
