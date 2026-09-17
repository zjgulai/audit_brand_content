#!/usr/bin/env python3
"""
verify_kb.py —— 需求知识库 · G1 验收器（机器可判定）

G1「存在性」的验收标准（建设方案 §二）：
    台账条数 = 各源系统可读条数之和；逐条回读比对 零丢失 / 零重复 / 零字段错位

本脚本把这句话拆成可执行的检查项，任何一项失败即退出码非 0。
**独立于生成器**：直接从快照原值与 schema 重算，不调用 tools/kb_build.py 的内部函数。

检查项：
  C1 计数守恒      台账真实条数 == 覆盖报告中所有 included 表的源条数之和
  C2 主键唯一      record_key 无重复
  C3 溯源可解      每条台账记录都能在快照里按 (系统,表,record_id) 找到
  C4 原文保真      status_raw / title(verbatim) 与快照原值逐条一致
  C5 状态归一      归一结果与 schema 声明一致；无"有值但未归一"
  C6 层级守恒      顶层 + 子任务 == 总数；子任务必须有 parent_record_id
  C7 覆盖完整      快照里每张表都出现在覆盖报告中（进或不进都要有理由）
  C8 敏感排除      排除表有占位记录，且其记录未进台账
  C9 可复现        台账的 fingerprint 重算一致
  C10 飞书回读     （若已落库）飞书条数与台账一致 —— 未落库时 SKIP，不算通过

★ E 组（B3.0 新增）守的是**治理**，不是数字：
  E1 缺口登记引用完整  每处 GAP 结论都必须带 〔缺口:ID〕，且该 ID 在 缺口-v1.json 里真实存在
                      —— 取代原先那条写成 `True` 的恒真检查（见 §D2 的历史）
  E2 缺口量可重算     每条缺口的「量」都要在 kb_facts 里重算对上；算不出来的必须显式声明
  E3 台账与快照同代    台账的 snapshot_id 必须等于当前快照 —— 基准日建在这上面
  E4 文档可重算        README 事实块与查询手册都必须是重算结果，手改/过期即红

用法：
  python3 tools/verify_kb.py
  python3 tools/verify_kb.py --json      # 机器可读
"""

import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "research", "kb"))
import load  # noqa: E402

SCHEMA = os.path.join(load.KB, "schema-v1.json")
LEDGER = os.path.join(load.KB, "台账-v1.json")
COVERAGE = os.path.join(load.KB, "覆盖报告.json")
ROUNDTRIP = os.path.join(load.KB, "_evidence", "feishu-roundtrip.json")


class Checks:
    def __init__(self):
        self.items = []

    def add(self, cid, name, ok, detail, skipped=False):
        self.items.append({"id": cid, "name": name,
                           "status": "SKIP" if skipped else ("PASS" if ok else "FAIL"),
                           "detail": detail})

    @property
    def failed(self):
        return [i for i in self.items if i["status"] == "FAIL"]

    @property
    def skipped(self):
        return [i for i in self.items if i["status"] == "SKIP"]


def main():
    as_json = "--json" in sys.argv
    schema = json.load(open(SCHEMA, encoding="utf-8"))
    ledger_doc = json.load(open(LEDGER, encoding="utf-8"))
    cov_doc = json.load(open(COVERAGE, encoding="utf-8"))
    snap = load.snapshot()
    c = Checks()

    records = ledger_doc["records"]
    real = [r for r in records if r["role"] != "excluded"]
    placeholder = [r for r in records if r["role"] == "excluded"]

    # ── C1 计数守恒 ──────────────────────────────────────────
    included = [x for x in cov_doc["coverage"] if x["included"]]
    expect = sum(x["source_records"] for x in included)
    c.add("C1", "计数守恒", len(real) == expect,
          f"台账 {len(real)} 条 vs 覆盖报告 included 源条数之和 {expect}")

    # ── C2 主键唯一 ──────────────────────────────────────────
    keys = [r["record_key"] for r in records]
    dup = [k for k, n in __import__("collections").Counter(keys).items() if n > 1]
    c.add("C2", "主键唯一", not dup, f"{len(keys)} 个键，重复 {len(dup)} 个" +
          (f"：{dup[:3]}" if dup else ""))

    # ── C3 溯源可解 ──────────────────────────────────────────
    missing = []
    srcmap = {}
    for spec in schema["tables"]:
        t = snap[(spec["system"], spec["name"])]
        for r in t.records:
            srcmap[(spec["system"], spec["table_id"], r["record_id"])] = r
    for r in real:
        k = (r["source_system"], r["source_table_id"], r["source_record_id"])
        if k not in srcmap:
            missing.append(r["record_key"])
    c.add("C3", "溯源可解", not missing,
          f"{len(real)} 条全部命中快照" if not missing else f"{len(missing)} 条指向不存在的源记录")

    # ── C4 原文保真 ──────────────────────────────────────────
    title_bad, status_bad, verbatim = [], [], 0
    for r in real:
        src = srcmap[(r["source_system"], r["source_table_id"], r["source_record_id"])]
        spec = next(s for s in schema["tables"]
                    if s["table_id"] == r["source_table_id"])
        m = spec["map"]
        if m.get("status_raw"):
            if load.flat(src["fields"].get(m["status_raw"])) != r["status_raw"]:
                status_bad.append(r["record_key"])
        if m.get("title") and r["title_source"] == "verbatim":
            verbatim += 1
            if load.flat(src["fields"].get(m["title"])) != r["title"]:
                title_bad.append(r["record_key"])
    ok4 = not title_bad and not status_bad
    c.add("C4", "原文保真", ok4,
          f"status_raw {len(real)} 条一致；verbatim 标题 {verbatim} 条一致"
          if ok4 else f"标题 {len(title_bad)} 条、状态 {len(status_bad)} 条与源不一致")

    # ── C5 状态归一 ──────────────────────────────────────────
    idx = {}
    for norm, raws in schema["status_normalization"].items():
        for x in raws:
            idx[x.strip().casefold()] = norm
    bad_norm = [r["record_key"] for r in real
                if r["status_raw"] and idx.get(str(r["status_raw"]).strip().casefold()) != r["status"]]
    unnorm = sorted({r["status_raw"] for r in real if r["status_raw"] and not r["status"]})
    c.add("C5", "状态归一", not bad_norm and not unnorm,
          f"归一后取值 {sorted({r['status'] for r in real if r['status']})}；"
          f"未归一 {len(unnorm)} 个" + (f"：{unnorm}" if unnorm else ""))

    # ── C6 层级守恒 ──────────────────────────────────────────
    top = sum(1 for r in real if r["level"] == "top")
    child = sum(1 for r in real if r["level"] == "child")
    orphan = [r["record_key"] for r in real if r["level"] == "child" and not r["parent_record_id"]]
    c.add("C6", "层级守恒", top + child == len(real) and not orphan,
          f"顶层 {top} + 子任务 {child} = {top + child}；无父的子任务 {len(orphan)}")

    # ── C7 覆盖完整 ──────────────────────────────────────────
    cov_keys = {(x["system"], x["table"]) for x in cov_doc["coverage"]}
    snap_keys = {(t.system, t.name) for t in snap.all()}
    uncovered = sorted(snap_keys - cov_keys)
    noreason = [f"{x['system']}:{x['table']}" for x in cov_doc["coverage"]
                if not x["included"] and not x.get("reason")]
    c.add("C7", "覆盖完整", not uncovered and not noreason,
          f"快照 {len(snap_keys)} 张表全部有覆盖记录；未进台账且无理由的 {len(noreason)} 张")

    # ── C8 敏感排除 ──────────────────────────────────────────
    excl_specs = schema.get("excluded_tables", [])
    excl_ids = {s["table_id"] for s in excl_specs}
    leaked = [r["record_key"] for r in real if r["source_table_id"] in excl_ids]
    have_ph = len(placeholder) == len(excl_specs)
    c.add("C8", "敏感排除", not leaked and have_ph,
          f"排除 {len(excl_specs)} 张表，占位 {len(placeholder)} 条，泄漏 {len(leaked)} 条")

    # ── C9 指纹可复算 ────────────────────────────────────────
    def fp(r):
        payload = {f: r.get(f) for f in ["title", "product_line", "sku", "status_raw",
                                         "priority_raw", "owner", "requester",
                                         "date_submitted", "date_due", "date_done"]}
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                         default=str).encode()).hexdigest()
    fp_bad = [r["record_key"] for r in real if fp(r) != r["fingerprint"]]
    c.add("C9", "指纹可复算", not fp_bad,
          f"{len(real)} 条指纹重算一致" if not fp_bad else f"{len(fp_bad)} 条指纹不符")

    # ── C10 飞书回读 ─────────────────────────────────────────
    if os.path.exists(ROUNDTRIP):
        rt = json.load(open(ROUNDTRIP, encoding="utf-8"))
        c.add("C10", "飞书回读", rt.get("match", False),
              f"飞书 {rt.get('feishu_records')} 条 vs 台账 {len(real)} 条；"
              f"缺失 {rt.get('missing')} / 多余 {rt.get('extra')} / 字段不符 {rt.get('mismatch')}")
    else:
        c.add("C10", "飞书回读", False,
              f"未找到 {os.path.relpath(ROUNDTRIP, load.REPO)}（落库后生成）", skipped=True)

    # ── D1-D3 G3 可用性：10 条黄金问题 ───────────────────────
    try:
        sys.path.insert(0, os.path.join(load.REPO, "tools"))
        import kb_query
        import kb_gaps
        import kb_facts
        empty = []
        gaps = []
        unregistered = []
        for i, (name, fn) in enumerate(kb_query.QUESTIONS, 1):
            try:
                lines = fn(ledger_doc, real)
            except Exception as e:                            # noqa: BLE001
                empty.append(f"Q{i}({type(e).__name__})")
                continue
            if not lines or not any(str(x).strip() for x in lines):
                empty.append(f"Q{i}")
            if any("GAP" in str(x) for x in lines):
                gaps.append(f"Q{i}")
            # ★ 每处 GAP 都必须带登记标记，且标记里的编号必须真实存在（E1）。
            #   这正是原来的 D2 想守、却写成 `True` 而永远守不住的东西。
            #   判据写成「**声明 GAP 的那条问题**至少有一处标记」，而不是「每行」——
            #   后者会把 GAP 的标题行本身算成违规（第一版就误报了）。
            if any("GAP" in str(x) for x in lines) and \
                    not any("〔缺口:" in str(x) for x in lines):
                unregistered.append(f"Q{i}: 声明了 GAP 却没有任何登记标记")
        c.add("D1", "黄金问题可答", not empty,
              f"{len(kb_query.QUESTIONS)} 条全部产出结论" if not empty
              else f"{len(empty)} 条答不出来：{empty}")

        # ── E1 缺口登记引用完整（取代原先恒为 True 的 D2）─────────
        #   ★ 一律读**盘上**的登记表：`kb_gaps.build()` 现算一份会让「登记表里
        #     有没有这一条」被自己回答 —— 第一版就是这样，检查恒绿。
        gap_path = os.path.join(load.KB, "缺口-v1.json")
        gap_doc = json.load(open(gap_path, encoding="utf-8")) if os.path.exists(gap_path) else None
        reg = {g["id"]: g for g in (gap_doc or {}).get("gaps", [])}
        seen_ids = set()
        missing = []
        for i, (name, fn) in enumerate(kb_query.QUESTIONS, 1):
            try:
                txt = "\n".join(str(x) for x in fn(ledger_doc, real))
            except Exception:                                 # noqa: BLE001
                continue
            for m in re.findall(r"〔缺口:([A-Za-z0-9_]+)〕", txt):
                seen_ids.add(m)
                if m not in reg:
                    missing.append(m)
        if gap_doc is None:
            missing.append("<缺口-v1.json 不存在>")
        e1_bad = list(unregistered) + missing
        c.add("E1", "缺口登记引用完整", not e1_bad,
              f"声明 GAP {len(gaps)} 处（{gaps if gaps else '无'}）；"
              f"引用登记编号 {sorted(seen_ids)}，登记表 {len(reg)} 条，"
              f"悬空 {len(missing)} 条"
              + (f"；无标记 {len(unregistered)} 处" if unregistered else "")
              + ("　✅ 每处 GAP 都指得出落点" if not e1_bad else ""))

        # ── E2 缺口的「量」必须可重算 ────────────────────────────
        facts = kb_facts.compute(snap)
        bad_qty, checked, unrecomp = [], 0, []
        for g in reg.values():
            if "量_unrecomputable" in g:
                unrecomp.append(g["id"])
                if "量" in g:
                    bad_qty.append(f"{g['id']}: 同时给了量又说不可重算")
                continue
            if "量" not in g:
                bad_qty.append(f"{g['id']}: 既没有量也没有量_unrecomputable —— 没人能核")
                continue
            for k, v in g["量"].items():
                checked += 1
                if k not in facts:
                    bad_qty.append(f"{g['id']}.{k}: kb_facts 里没有这个键")
                elif facts[k] != v:
                    bad_qty.append(f"{g['id']}.{k}: 登记 {v} vs 重算 {facts[k]}")
        c.add("E2", "缺口量可重算", not bad_qty,
              f"可重算键 {checked} 个全部对上；声明不可重算 {len(unrecomp)} 条"
              f"（{unrecomp}）" + ("" if not bad_qty else f"；❌ {bad_qty}"))

        # ── E5 缺口登记新鲜度 ────────────────────────────────────
        #   E1/E2 读的是盘上的制品，所以还必须有一条守「制品本身没过期」。
        #   没有它，改一次材料表却忘了重跑 kb_gaps.py，E1/E2 会全绿。
        want_gap = json.dumps(kb_gaps.build(facts, snap), ensure_ascii=False, indent=1) + "\n"
        have_gap = open(gap_path, encoding="utf-8").read() if os.path.exists(gap_path) else None
        c.add("E5", "缺口登记新鲜", have_gap == want_gap,
              (f"{os.path.relpath(gap_path, load.REPO)} 与重算一致（{len(reg)} 条）"
               if have_gap == want_gap else
               "❌ 登记表已过期 —— 修复：python3 tools/kb_gaps.py"))

        # ── E3 台账与快照同代（基准日、数字都建在这上面）──────────
        c.add("E3", "台账与快照同代",
              ledger_doc["snapshot_id"] == snap.snapshot_id,
              f"台账 {ledger_doc['snapshot_id']} vs 快照 {snap.snapshot_id}；"
              f"基准日 {load.basis_date(snap)}")

        # ── E4 文档事实块与查询手册都不许腐烂 ────────────────────
        want = kb_facts.render(facts)
        readme = os.path.join(load.KB, "README.md")
        have = kb_facts.current_block(open(readme, encoding="utf-8").read()) \
            if os.path.exists(readme) else None
        manual = os.path.join(load.KB, "查询手册.md")
        manual_have = open(manual, encoding="utf-8").read() if os.path.exists(manual) else None
        manual_want = kb_query.render_manual(
            ledger_doc, [(i, n, fn(ledger_doc, real))
                         for i, (n, fn) in enumerate(kb_query.QUESTIONS, 1)])
        c.add("E4", "文档可重算", have == want and manual_have == manual_want,
              f"README 事实块 {'一致' if have == want else '❌已过期'}；"
              f"查询手册 {'一致' if manual_have == manual_want else '❌已过期'}"
              f"（修复：python3 tools/kb_facts.py && python3 tools/kb_query.py --md）")

        manual = os.path.join(load.KB, "查询手册.md")
        n_sec = 0
        if os.path.exists(manual):
            n_sec = open(manual, encoding="utf-8").read().count("\n## Q")
        c.add("D3", "查询手册", n_sec >= 10,
              f"{os.path.relpath(manual, load.REPO)} 含 {n_sec} 条问题（需 ≥10）")
    except Exception as e:                                    # noqa: BLE001
        c.add("D1", "黄金问题可答", False, f"导入 kb_query 失败：{e}")

    # ── 汇总 ─────────────────────────────────────────────────
    result = {
        "schema_version": ledger_doc["schema_version"],
        "snapshot_id": ledger_doc["snapshot_id"],
        "ledger_records": len(real),
        "checks": c.items,
        "failed": len(c.failed),
        "skipped": len(c.skipped),
        "pass": not c.failed,
    }
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        print(f"═══ 验收 · 需求知识库（{ledger_doc['schema_version']}）═══")
        print(f"快照 {ledger_doc['snapshot_id']}　台账 {len(real)} 条 + {len(placeholder)} 条占位")
        print("　G1 存在性：")
        for i in c.items:
            if i["id"].startswith("C"):
                mark = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️ "}[i["status"]]
                print(f"  {mark} {i['id']:<4}{i['name']:<10} {i['detail']}")
        print("　G3 可用性：")
        for i in c.items:
            if i["id"].startswith("D"):
                mark = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️ "}[i["status"]]
                print(f"  {mark} {i['id']:<4}{i['name']:<10} {i['detail']}")
        print("　E 组 · 治理（缺口登记 / 文档可重算）：")
        for i in sorted((x for x in c.items if x["id"].startswith("E")),
                        key=lambda x: x["id"]):
                mark = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️ "}[i["status"]]
                print(f"  {mark} {i['id']:<4}{i['name']:<10} {i['detail']}")
        print()
        if c.failed:
            print(f"❌ {len(c.failed)} 项失败：{[i['id'] for i in c.failed]}")
        elif c.skipped:
            print(f"⚠️  无失败，但有 {len(c.skipped)} 项跳过 —— 尚未完整通过")
        else:
            print("✅ G1 + G3 全部通过")
    return 1 if c.failed else 0


if __name__ == "__main__":
    sys.exit(main())
